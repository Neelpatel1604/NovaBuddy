import os

import boto3
from boto3.dynamodb.conditions import Key

from shared.response import api_handler, success

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])

SUMMARY_FIELDS = [
    "lecture_id",
    "title",
    "content_type",
    "upload_timestamp",
]


@api_handler(requires_auth=True)
def handler(*, event, user_id, body, path_params, context):
    result = table.query(
        KeyConditionExpression=Key("user_id").eq(user_id),
        ProjectionExpression="lecture_id, title, content_type, upload_timestamp, summary",
    )
    items = result.get("Items", [])

    lectures = []
    for item in items:
        lectures.append(
            {
                "lectureId": item.get("lecture_id"),
                "title": item.get("title"),
                "contentType": item.get("content_type"),
                "uploadTimestamp": item.get("upload_timestamp"),
                "hasSummary": bool(item.get("summary")),
            }
        )

    return success(lectures)
