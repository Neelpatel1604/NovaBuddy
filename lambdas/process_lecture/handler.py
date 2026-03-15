import json
import logging
import os

import boto3

from shared.bedrock import converse, converse_with_document
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


@api_handler(requires_auth=True)
def handler(*, event, user_id, body, path_params, context):
    lecture_id = path_params.get("lectureId")
    if not lecture_id:
        return error("lectureId path parameter is required", 400)

    result = table.get_item(Key={"user_id": user_id, "lecture_id": lecture_id})
    item = result.get("Item")
    if not item:
        return error("Lecture not found", 404)

    s3_key = item.get("s3_key")
    content_type = item.get("content_type", "application/pdf")

    if body.get("title"):
        table.update_item(
            Key={"user_id": user_id, "lecture_id": lecture_id},
            UpdateExpression="SET title = :t",
            ExpressionAttributeValues={":t": body["title"]},
        )

    logger.info("Downloading s3://%s/%s", bucket, s3_key)
    obj = s3.get_object(Bucket=bucket, Key=s3_key)
    file_bytes = obj["Body"].read()

    # --- Step 1: Extract text from the document ---
    logger.info("Step 1: Extracting text via Nova (content_type=%s)", content_type)
    processed_text = converse_with_document(
        file_bytes=file_bytes,
        content_type=content_type,
        prompt=EXTRACT_PROMPT,
        max_tokens=4096,
    )

    # --- Step 2: Generate study aids from extracted text ---
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

    # --- Step 3: Persist results ---
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

    return success(
        {
            "status": "completed",
            "lectureId": lecture_id,
            "summary": summary,
            "quizQuestionCount": len(json.loads(quiz_json)),
            "keyConcepts": key_concepts,
        }
    )
