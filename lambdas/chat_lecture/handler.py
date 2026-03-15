import os

import boto3

from shared.bedrock import converse
from shared.response import api_handler, success, error

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])

CHAT_SYSTEM_PROMPT = (
    "You are NovaBuddy, a helpful and accurate study assistant. "
    "Answer the student's question based ONLY on the lecture content provided below. "
    "If the answer is not in the lecture material, say so clearly. "
    "Cite specific sections when possible. Use clear, concise language appropriate for a student."
)


@api_handler(requires_auth=True)
def handler(*, event, user_id, body, path_params, context):
    lecture_id = path_params.get("lectureId")
    if not lecture_id:
        return error("lectureId path parameter is required", 400)

    message = body.get("message", "").strip()
    if not message:
        return error("message is required", 400)

    history = body.get("history", [])

    result = table.get_item(
        Key={"user_id": user_id, "lecture_id": lecture_id},
        ProjectionExpression="processed_text, title",
    )
    item = result.get("Item")
    if not item:
        return error("Lecture not found", 404)

    processed_text = item.get("processed_text")
    if not processed_text:
        return error("Lecture has not been processed yet. Call /process first.", 400)

    title = item.get("title", "Untitled")
    system = f"{CHAT_SYSTEM_PROMPT}\n\n--- LECTURE: {title} ---\n\n{processed_text[:15000]}"

    messages = []
    for entry in history[-10:]:
        role = entry.get("role")
        content = entry.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": [{"text": content}]})

    messages.append({"role": "user", "content": [{"text": message}]})

    reply = converse(
        messages=messages,
        system_prompt=system,
        max_tokens=2048,
        temperature=0.3,
    )

    return success({"reply": reply})
