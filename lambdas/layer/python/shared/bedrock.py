import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("BEDROCK_REGION", "us-east-1"),
        )
    return _client


DOCUMENT_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "text/csv": "csv",
    "text/html": "html",
    "text/plain": "txt",
    "text/markdown": "md",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}

IMAGE_CONTENT_TYPES = {
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


def build_document_block(file_bytes: bytes, content_type: str, name: str = "upload"):
    """Build a Converse API content block for a document or image."""
    if content_type in IMAGE_CONTENT_TYPES:
        return {
            "image": {
                "format": IMAGE_CONTENT_TYPES[content_type],
                "source": {"bytes": file_bytes},
            }
        }
    if content_type in DOCUMENT_CONTENT_TYPES:
        return {
            "document": {
                "format": DOCUMENT_CONTENT_TYPES[content_type],
                "name": name,
                "source": {"bytes": file_bytes},
            }
        }
    raise ValueError(f"Unsupported content type: {content_type}")


def converse(messages, system_prompt=None, model_id=None, max_tokens=4096, temperature=0.3):
    """Call Bedrock Converse API and return the text response."""
    client = _get_client()
    model = model_id or os.environ.get("MODEL_ID", "amazon.nova-lite-v1:0")

    kwargs = {
        "modelId": model,
        "messages": messages,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]

    logger.info("Calling Bedrock Converse with model=%s, messages=%d", model, len(messages))
    response = client.converse(**kwargs)

    output = response.get("output", {})
    message = output.get("message", {})
    content_blocks = message.get("content", [])

    texts = [block["text"] for block in content_blocks if "text" in block]
    return "\n".join(texts)


def converse_with_document(file_bytes, content_type, prompt, system_prompt=None, model_id=None, max_tokens=4096):
    """Send a document/image to Nova with a text prompt and return the response."""
    doc_block = build_document_block(file_bytes, content_type)
    messages = [
        {
            "role": "user",
            "content": [doc_block, {"text": prompt}],
        }
    ]
    return converse(messages, system_prompt=system_prompt, model_id=model_id, max_tokens=max_tokens)
