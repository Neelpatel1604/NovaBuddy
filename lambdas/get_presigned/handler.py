import os
import uuid
from datetime import datetime, timezone

import boto3

from shared.response import api_handler, success, error

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
bucket = os.environ["UPLOAD_BUCKET_NAME"]

# Map file extensions to MIME types (frontend sends filename only)
EXT_TO_MIME = {
    ".pdf": "application/pdf",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


def _content_type_from_filename(filename: str) -> str:
    ext = os.path.splitext(filename.lower())[1]
    return EXT_TO_MIME.get(ext, "application/octet-stream")


@api_handler(requires_auth=True)
def handler(*, event, user_id, body, path_params, context):
    """
    Accepts filename only. Infers content type from extension and returns
    presigned S3 PUT URL for frontend to upload the file.
    """
    filename = body.get("filename")

    if not filename:
        return error("filename is required", 400)

    content_type = _content_type_from_filename(filename)

    # Block unsupported types early so /process doesn't fail later
    if content_type.startswith("video/"):
        return error(
            "Video files are not supported. Please upload PDFs, Word docs, PowerPoint, text, or images.",
            400,
        )

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
