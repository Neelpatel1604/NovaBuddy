import json
import logging
import os

import boto3

from shared.bedrock import (
    converse,
    converse_with_document,
    DOCUMENT_CONTENT_TYPES,
    IMAGE_CONTENT_TYPES,
)
from shared.response import api_handler, success, error

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
bucket = os.environ["UPLOAD_BUCKET_NAME"]

EXTRACT_PROMPT = (
    "Extract ALL text content from this document verbatim. "
    "Include every heading, paragraph, bullet point, caption, and table content. "
    "Preserve the logical structure using markdown formatting. "
    "Do NOT summarize — output the complete text."
)

STUDY_AIDS_SYSTEM = (
    "You are NovaBuddy, an expert academic tutor. "
    "Generate study materials that are accurate, clear, and useful for exam preparation."
)

STUDY_AIDS_PROMPT = """Analyze the following lecture content and produce three outputs in the exact JSON structure below.

LECTURE CONTENT:
{text}

---

Return ONLY valid JSON with this schema (no markdown fences, no extra text):
{{
  "summary": "A 300-500 word markdown summary covering all major topics and key takeaways.",
  "quiz": [
    {{
      "type": "mcq",
      "question": "...",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "answer": "A",
      "explanation": "..."
    }},
    {{
      "type": "short_answer",
      "question": "...",
      "answer": "...",
      "explanation": "..."
    }}
  ],
  "key_concepts": "A markdown list of 8-15 key concepts with brief definitions."
}}

Generate 8-12 quiz questions (mix of mcq and short_answer). Ensure questions span the full breadth of the material."""


def _process_item(item: dict, title_override: str | None = None) -> dict:
    """Core processing logic shared by API and S3 triggers."""
    user_id = item["user_id"]
    lecture_id = item["lecture_id"]

    # Already processed — skip heavy work
    if item.get("summary"):
        return {
            "status": "completed",
            "lectureId": lecture_id,
            "summary": item.get("summary"),
            "quizQuestionCount": len(json.loads(item.get("quiz_json") or "[]")),
            "keyConcepts": item.get("key_concepts", ""),
        }

    s3_key = item.get("s3_key")
    content_type = item.get("content_type", "application/pdf")

    if content_type not in DOCUMENT_CONTENT_TYPES and content_type not in IMAGE_CONTENT_TYPES:
        raise ValueError(
            f"Unsupported content type for processing: {content_type}. "
            "Please upload PDFs, Word docs, PowerPoint, text/markdown, or common image formats."
        )

    if title_override:
        table.update_item(
            Key={"user_id": user_id, "lecture_id": lecture_id},
            UpdateExpression="SET title = :t",
            ExpressionAttributeValues={":t": title_override},
        )

    logger.info("Downloading s3://%s/%s", bucket, s3_key)
    obj = s3.get_object(Bucket=bucket, Key=s3_key)
    file_bytes = obj["Body"].read()

    # Step 1: extract text
    logger.info("Step 1: Extracting text via Nova (content_type=%s)", content_type)
    processed_text = converse_with_document(
        file_bytes=file_bytes,
        content_type=content_type,
        prompt=EXTRACT_PROMPT,
        max_tokens=4096,
    )

    # Step 2: generate study aids
    logger.info("Step 2: Generating study aids via Nova")
    study_prompt = STUDY_AIDS_PROMPT.format(text=processed_text[:12000])
    messages = [{"role": "user", "content": [{"text": study_prompt}]}]
    raw_output = converse(
        messages=messages,
        system_prompt=STUDY_AIDS_SYSTEM,
        max_tokens=4096,
        temperature=0.4,
    )

    summary = ""
    quiz_json = "[]"
    key_concepts = ""

    try:
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        parsed = json.loads(cleaned)
        summary = parsed.get("summary", "")
        quiz_json = json.dumps(parsed.get("quiz", []))
        key_concepts = parsed.get("key_concepts", "")
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning("Failed to parse study aids JSON, storing raw: %s", e)
        summary = raw_output
        quiz_json = "[]"
        key_concepts = ""

    # Step 3: persist results
    table.update_item(
        Key={"user_id": user_id, "lecture_id": lecture_id},
        UpdateExpression=(
            "SET processed_text = :pt, summary = :s, quiz_json = :q, key_concepts = :kc"
        ),
        ExpressionAttributeValues={
            ":pt": processed_text,
            ":s": summary,
            ":q": quiz_json,
            ":kc": key_concepts,
        },
    )

    return {
        "status": "completed",
        "lectureId": lecture_id,
        "summary": summary,
        "quizQuestionCount": len(json.loads(quiz_json)),
        "keyConcepts": key_concepts,
    }


def _find_item_by_s3_key(s3_key: str) -> dict | None:
    """Lookup lecture row by s3_key (used by S3 trigger path)."""
    resp = table.scan(
        FilterExpression="s3_key = :k",
        ExpressionAttributeValues={":k": s3_key},
    )
    items = resp.get("Items") or []
    return items[0] if items else None


@api_handler(requires_auth=True)
def http_handler(*, event, user_id, body, path_params, context):
    lecture_id = path_params.get("lectureId")
    if not lecture_id:
        return error("lectureId path parameter is required", 400)

    result = table.get_item(Key={"user_id": user_id, "lecture_id": lecture_id})
    item = result.get("Item")
    if not item:
        return error("Lecture not found", 404)

    try:
        output = _process_item(item, title_override=body.get("title"))
    except ValueError as e:
        return error(str(e), 400)

    return success(output)


def handler(event, context):
    """
    Lambda entrypoint that supports both:
    - API Gateway (manual POST /process) via http_handler
    - S3 ObjectCreated events for automatic processing
    """
    # S3 trigger path
    if "Records" in event:
        records = event.get("Records") or []
        for record in records:
            s3_info = record.get("s3", {})
            key = s3_info.get("object", {}).get("key")
            if not key:
                logger.warning("Missing key in S3 record: %s", json.dumps(record))
                continue

            try:
                item = _find_item_by_s3_key(key)
                if not item:
                    logger.warning("No lecture item found for s3_key=%s", key)
                    continue

                # Core function will skip if already processed
                _process_item(item)
            except Exception as e:
                logger.exception("Failed to auto-process key=%s: %s", key, e)
        # S3 invokes don't need HTTP-style response
        return

    # Fallback to HTTP API handler
    return http_handler(event=event, context=context)
