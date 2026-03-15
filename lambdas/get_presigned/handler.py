import os
import uuid
from datetime import datetime, timezone

import boto3

from shared.response import api_handler, success, error

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
bucket = os.environ["UPLOAD_BUCKET_NAME"]


@api_handler(requires_auth=True)
def handler(*, event, user_id, body, path_params, context):
    filename = body.get("filename")
    content_type = body.get("contentType")

    if not filename or not content_type:
        return error("filename and contentType are required", 400)

    lecture_id = str(uuid.uuid4())
    s3_key = f"{user_id}/{lecture_id}/{filename}"

    presigned_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=600,
    )

    table.put_item(
        Item={
            "user_id": user_id,
            "lecture_id": lecture_id,
            "title": filename,
            "s3_key": s3_key,
            "content_type": content_type,
            "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    return success({"url": presigned_url, "lectureId": lecture_id})
