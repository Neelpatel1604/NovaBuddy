"""
Generate summary video for a lecture using Amazon Nova Reel.
Uses inference profile (e.g. us.amazon.nova-reel-v1:1) for US geographic inference.
The summary text is used to create a 6-second video (text-to-video).
Returns a presigned URL for the frontend to play.
Cached: if already generated, returns URL immediately.
"""
import logging
import os
import re
import time
from urllib.parse import urlparse

import boto3

from shared.response import api_handler, success, error

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Nova Reel model ID (Bedrock) – default to amazon.nova-reel-v1:1
NOVA_REEL_MODEL = os.environ.get("NOVA_REEL_INFERENCE_PROFILE", "amazon.nova-reel-v1:1")
MAX_TEXT_LENGTH = 512
POLL_INTERVAL_SEC = 10
MAX_POLL_TIME_SEC = 240

bedrock = boto3.client("bedrock-runtime")
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
bucket = os.environ["GENERATED_BUCKET_NAME"]


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting for cleaner video prompt."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{2,}", " ", text)
    return text.strip()


def _extract_invocation_id(invocation_arn: str) -> str:
    """Extract invocation ID from ARN (format: ...:async-invoke/invocation-id)."""
    return invocation_arn.split("/")[-1]


@api_handler(requires_auth=True)
def handler(*, event, user_id, body, path_params, context):
    lecture_id = path_params.get("lectureId")
    if not lecture_id:
        return error("lectureId path parameter is required", 400)

    result = table.get_item(
        Key={"user_id": user_id, "lecture_id": lecture_id},
        ProjectionExpression="summary, summary_video_key",
    )
    item = result.get("Item")
    if not item:
        return error("Lecture not found", 404)

    summary = item.get("summary", "").strip()
    if not summary:
        return error("Lecture has not been processed yet. Call /process first.", 400)

    # Check cache: already generated
    existing_key = item.get("summary_video_key")
    if existing_key:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": existing_key},
            ExpiresIn=3600,
        )
        return success({"url": url, "expiresIn": 3600, "cached": True, "format": "mp4"})

    # Prepare text prompt (Nova Reel limit 512 chars)
    text = _strip_markdown(summary)
    if len(text) > MAX_TEXT_LENGTH:
        text = text[: MAX_TEXT_LENGTH - 3] + "..."

    s3_uri = f"s3://{bucket}/{user_id}/{lecture_id}/"
    model_input = {
        "taskType": "TEXT_VIDEO",
        "textToVideoParams": {"text": text},
        "videoGenerationConfig": {
            "durationSeconds": 6,
            "fps": 24,
            "dimension": "1280x720",
            "seed": 42,
        },
    }

    try:
        response = bedrock.start_async_invoke(
            modelId=NOVA_REEL_MODEL,
            modelInput=model_input,
            outputDataConfig={"s3OutputDataConfig": {"s3Uri": s3_uri}},
        )
    except Exception as e:
        logger.error("Nova Reel start_async_invoke failed: %s", str(e))
        return error(f"Failed to start video generation: {str(e)}", 500)

    invocation_arn = response.get("invocationArn")
    if not invocation_arn:
        return error("No invocation ARN in response", 500)

    # Poll until complete (typical ~90 sec for 6s video)
    start = time.time()
    status_response = None
    while time.time() - start < MAX_POLL_TIME_SEC:
        status_response = bedrock.get_async_invoke(invocationArn=invocation_arn)
        status = status_response.get("status")
        logger.info("Nova Reel job status: %s", status)

        if status == "Completed":
            break
        if status == "Failed":
            msg = status_response.get("failureMessage", "Unknown failure")
            logger.error("Nova Reel job failed: %s", msg)
            return error(f"Video generation failed: {msg}", 500)

        time.sleep(POLL_INTERVAL_SEC)

    if not status_response or status_response.get("status") != "Completed":
        return error("Video generation timed out. Try again later.", 504)

    # Get output path from response
    output_config = status_response.get("outputDataConfig", {}).get(
        "s3OutputDataConfig", {}
    )
    output_uri = output_config.get("s3Uri") or f"{s3_uri}{_extract_invocation_id(invocation_arn)}"
    if output_uri.startswith("s3://"):
        parsed = urlparse(output_uri)
        key_prefix = parsed.path.lstrip("/")
        s3_key = f"{key_prefix}/output.mp4"
    else:
        inv_id = _extract_invocation_id(invocation_arn)
        s3_key = f"{user_id}/{lecture_id}/{inv_id}/output.mp4"

    table.update_item(
        Key={"user_id": user_id, "lecture_id": lecture_id},
        UpdateExpression="SET summary_video_key = :k",
        ExpressionAttributeValues={":k": s3_key},
    )

    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=3600,
    )

    return success({"url": url, "expiresIn": 3600, "cached": False, "format": "mp4"})
