import json
import logging
import traceback
from functools import wraps

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
}


def success(body, status_code=200):
    return {
        "statusCode": status_code,
        "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def error(message, status_code=400):
    return {
        "statusCode": status_code,
        "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }


def api_handler(requires_auth=True):
    """Decorator that extracts user_id, parses body, and handles errors."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(event, context):
            try:
                user_id = None
                if requires_auth:
                    claims = (
                        event.get("requestContext", {})
                        .get("authorizer", {})
                        .get("jwt", {})
                        .get("claims", {})
                    )
                    user_id = claims.get("sub")
                    if not user_id:
                        return error("Unauthorized", 401)

                body = {}
                raw = event.get("body")
                if raw:
                    body = json.loads(raw) if isinstance(raw, str) else raw

                path_params = event.get("pathParameters") or {}

                return fn(
                    event=event,
                    user_id=user_id,
                    body=body,
                    path_params=path_params,
                    context=context,
                )
            except json.JSONDecodeError:
                return error("Invalid JSON in request body", 400)
            except Exception as e:
                logger.error("Unhandled exception: %s\n%s", str(e), traceback.format_exc())
                return error("Internal server error", 500)

        return wrapper

    return decorator
