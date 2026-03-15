import os

import boto3

from shared.response import api_handler, success, error

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])


@api_handler(requires_auth=True)
def handler(*, event, user_id, body, path_params, context):
    lecture_id = path_params.get("lectureId")
    if not lecture_id:
        return error("lectureId path parameter is required", 400)

    result = table.get_item(Key={"user_id": user_id, "lecture_id": lecture_id})
    item = result.get("Item")

    if not item:
        return error("Lecture not found", 404)

    return success(
        {
            "lectureId": item.get("lecture_id"),
            "title": item.get("title"),
            "contentType": item.get("content_type"),
            "uploadTimestamp": item.get("upload_timestamp"),
            "s3Key": item.get("s3_key"),
            "summary": item.get("summary"),
            "quizJson": item.get("quiz_json"),
            "keyConcepts": item.get("key_concepts"),
            "processedText": item.get("processed_text"),
        }
    )
