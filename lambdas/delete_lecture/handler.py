import os

import boto3

from shared.response import api_handler, success, error

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
bucket = os.environ["UPLOAD_BUCKET_NAME"]


@api_handler(requires_auth=True)
def handler(*, event, user_id, body, path_params, context):
    lecture_id = path_params.get("lectureId")
    if not lecture_id:
        return error("lectureId path parameter is required", 400)

    result = table.get_item(
        Key={"user_id": user_id, "lecture_id": lecture_id},
        ProjectionExpression="s3_key",
    )
    item = result.get("Item")
    if not item:
        return error("Lecture not found", 404)

    s3_key = item.get("s3_key")
    if s3_key:
        s3.delete_object(Bucket=bucket, Key=s3_key)

    table.delete_item(Key={"user_id": user_id, "lecture_id": lecture_id})

    return success({"deleted": True})
