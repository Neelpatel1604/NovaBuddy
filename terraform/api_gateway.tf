# ── HTTP API ───────────────────────────────────────────────────────

resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_headers = ["Content-Type", "Authorization"]
    allow_methods = ["GET", "POST", "DELETE", "OPTIONS"]
    allow_origins = ["*"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      errorMessage   = "$context.error.message"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigateway/${local.name_prefix}"
  retention_in_days = 7
}

# ── JWT Authorizer (Cognito) ──────────────────────────────────────

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.main.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "cognito-jwt"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.main.id]
    issuer   = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
  }
}

# ── Integrations ──────────────────────────────────────────────────

resource "aws_apigatewayv2_integration" "health" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.health.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "get_presigned" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.get_presigned.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "process_lecture" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.process_lecture.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "list_lectures" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.list_lectures.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "get_lecture" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.get_lecture.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "chat_lecture" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.chat_lecture.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "delete_lecture" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.delete_lecture.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "generate_lecture_video" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.generate_lecture_video.invoke_arn
  payload_format_version = "2.0"
}

# ── Routes ────────────────────────────────────────────────────────

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /api/v1/health"
  target    = "integrations/${aws_apigatewayv2_integration.health.id}"
}

resource "aws_apigatewayv2_route" "upload_presigned" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /api/v1/upload/presigned"
  target             = "integrations/${aws_apigatewayv2_integration.get_presigned.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "process_lecture" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /api/v1/lectures/{lectureId}/process"
  target             = "integrations/${aws_apigatewayv2_integration.process_lecture.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "list_lectures" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /api/v1/lectures"
  target             = "integrations/${aws_apigatewayv2_integration.list_lectures.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "get_lecture" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /api/v1/lectures/{lectureId}"
  target             = "integrations/${aws_apigatewayv2_integration.get_lecture.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "chat_lecture" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /api/v1/lectures/{lectureId}/chat"
  target             = "integrations/${aws_apigatewayv2_integration.chat_lecture.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "delete_lecture" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "DELETE /api/v1/lectures/{lectureId}"
  target             = "integrations/${aws_apigatewayv2_integration.delete_lecture.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "generate_lecture_video" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /api/v1/lectures/{lectureId}/video"
  target             = "integrations/${aws_apigatewayv2_integration.generate_lecture_video.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}
