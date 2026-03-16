# ── IAM Role ───────────────────────────────────────────────────────

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name_prefix}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda_permissions" {
  # CloudWatch Logs
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }

  # DynamoDB
  statement {
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
    ]
    resources = [aws_dynamodb_table.lectures.arn]
  }

  # S3 (uploads bucket - user lecture files)
  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]
  }

  # S3 (generated bucket - summary audio, video outputs)
  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.generated.arn}/*"]
  }

  # Bedrock sync (Converse, etc.) + US inference
  statement {
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = [
      # Public foundation models (no account id)
      "arn:aws:bedrock:${var.region}::foundation-model/*",
      "arn:aws:bedrock:${var.region}::us.foundation-model/*",
      # Account‑scoped models (custom / inference profiles that resolve to models in this account)
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:foundation-model/*",
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:us.foundation-model/*",
    ]
  }

  # Bedrock async (Nova Reel video - StartAsyncInvoke)
  statement {
    actions = [
      "bedrock:InvokeModel",
      "bedrock:StartAsyncInvoke",
      "bedrock:GetAsyncInvoke",
      "bedrock:ListAsyncInvokes",
    ]
    resources = [
      # Public foundation models (no account id)
      "arn:aws:bedrock:${var.region}::foundation-model/*",
      "arn:aws:bedrock:${var.region}::us.foundation-model/*",
      # Account‑scoped models (custom / inference profiles that resolve to models in this account)
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:foundation-model/*",
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:us.foundation-model/*",
      # Async invoke jobs
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:async-invoke/*",
    ]
  }

  # Polly (text-to-speech - fallback/legacy)
  statement {
    actions   = ["polly:SynthesizeSpeech"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.name_prefix}-lambda-policy"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_permissions.json
}

# ── Lambda Layer (shared code) ─────────────────────────────────────

data "archive_file" "shared_layer" {
  type        = "zip"
  source_dir  = "${local.lambdas_dir}/layer"
  output_path = "${path.module}/.build/layer.zip"
}

resource "aws_lambda_layer_version" "shared" {
  layer_name          = "${local.name_prefix}-shared"
  filename            = data.archive_file.shared_layer.output_path
  source_code_hash    = data.archive_file.shared_layer.output_base64sha256
  compatible_runtimes = ["python3.12", "python3.13"]
}

# ── Lambda Function Archives ──────────────────────────────────────

data "archive_file" "health" {
  type        = "zip"
  source_dir  = "${local.lambdas_dir}/health"
  output_path = "${path.module}/.build/health.zip"
}

data "archive_file" "get_presigned" {
  type        = "zip"
  source_dir  = "${local.lambdas_dir}/get_presigned"
  output_path = "${path.module}/.build/get_presigned.zip"
}

data "archive_file" "process_lecture" {
  type        = "zip"
  source_dir  = "${local.lambdas_dir}/process_lecture"
  output_path = "${path.module}/.build/process_lecture.zip"
}

data "archive_file" "list_lectures" {
  type        = "zip"
  source_dir  = "${local.lambdas_dir}/list_lectures"
  output_path = "${path.module}/.build/list_lectures.zip"
}

data "archive_file" "get_lecture" {
  type        = "zip"
  source_dir  = "${local.lambdas_dir}/get_lecture"
  output_path = "${path.module}/.build/get_lecture.zip"
}

data "archive_file" "chat_lecture" {
  type        = "zip"
  source_dir  = "${local.lambdas_dir}/chat_lecture"
  output_path = "${path.module}/.build/chat_lecture.zip"
}

data "archive_file" "delete_lecture" {
  type        = "zip"
  source_dir  = "${local.lambdas_dir}/delete_lecture"
  output_path = "${path.module}/.build/delete_lecture.zip"
}

data "archive_file" "generate_lecture_video" {
  type        = "zip"
  source_dir  = "${local.lambdas_dir}/generate_lecture_video"
  output_path = "${path.module}/.build/generate_lecture_video.zip"
}

# ── Lambda Functions ──────────────────────────────────────────────

locals {
  common_env = {
    BEDROCK_REGION       = var.region
    MODEL_ID             = var.model_id
    EMBEDDING_MODEL_ID   = var.embedding_model_id
    UPLOAD_BUCKET_NAME   = aws_s3_bucket.uploads.id
    GENERATED_BUCKET_NAME = aws_s3_bucket.generated.id
    DYNAMODB_TABLE       = aws_dynamodb_table.lectures.name
  }
}

resource "aws_lambda_function" "health" {
  function_name    = "${local.name_prefix}-health"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.health.output_path
  source_code_hash = data.archive_file.health.output_base64sha256
  timeout          = 10
  memory_size      = 128
}

resource "aws_lambda_function" "get_presigned" {
  function_name    = "${local.name_prefix}-get-presigned"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.get_presigned.output_path
  source_code_hash = data.archive_file.get_presigned.output_base64sha256
  timeout          = 15
  memory_size      = 128
  layers           = [aws_lambda_layer_version.shared.arn]

  environment {
    variables = local.common_env
  }
}

resource "aws_lambda_function" "process_lecture" {
  function_name    = "${local.name_prefix}-process-lecture"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.process_lecture.output_path
  source_code_hash = data.archive_file.process_lecture.output_base64sha256
  timeout          = 300
  memory_size      = 512
  layers           = [aws_lambda_layer_version.shared.arn]

  environment {
    variables = local.common_env
  }
}

resource "aws_lambda_function" "list_lectures" {
  function_name    = "${local.name_prefix}-list-lectures"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.list_lectures.output_path
  source_code_hash = data.archive_file.list_lectures.output_base64sha256
  timeout          = 15
  memory_size      = 128
  layers           = [aws_lambda_layer_version.shared.arn]

  environment {
    variables = local.common_env
  }
}

resource "aws_lambda_function" "get_lecture" {
  function_name    = "${local.name_prefix}-get-lecture"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.get_lecture.output_path
  source_code_hash = data.archive_file.get_lecture.output_base64sha256
  timeout          = 15
  memory_size      = 128
  layers           = [aws_lambda_layer_version.shared.arn]

  environment {
    variables = local.common_env
  }
}

resource "aws_lambda_function" "chat_lecture" {
  function_name    = "${local.name_prefix}-chat-lecture"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.chat_lecture.output_path
  source_code_hash = data.archive_file.chat_lecture.output_base64sha256
  timeout          = 120
  memory_size      = 256
  layers           = [aws_lambda_layer_version.shared.arn]

  environment {
    variables = local.common_env
  }
}

resource "aws_lambda_function" "delete_lecture" {
  function_name    = "${local.name_prefix}-delete-lecture"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.delete_lecture.output_path
  source_code_hash = data.archive_file.delete_lecture.output_base64sha256
  timeout          = 15
  memory_size      = 128
  layers           = [aws_lambda_layer_version.shared.arn]

  environment {
    variables = local.common_env
  }
}

resource "aws_lambda_function" "generate_lecture_video" {
  function_name    = "${local.name_prefix}-generate-lecture-video"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.generate_lecture_video.output_path
  source_code_hash = data.archive_file.generate_lecture_video.output_base64sha256
  timeout          = 300
  memory_size      = 256
  layers           = [aws_lambda_layer_version.shared.arn]

  environment {
    variables = merge(local.common_env, {
      NOVA_REEL_INFERENCE_PROFILE = var.nova_reel_inference_profile
    })
  }
}

# ── API Gateway Permissions ───────────────────────────────────────

locals {
  lambda_functions = {
    health                 = aws_lambda_function.health
    get_presigned          = aws_lambda_function.get_presigned
    process_lecture        = aws_lambda_function.process_lecture
    list_lectures          = aws_lambda_function.list_lectures
    get_lecture            = aws_lambda_function.get_lecture
    chat_lecture           = aws_lambda_function.chat_lecture
    delete_lecture         = aws_lambda_function.delete_lecture
    generate_lecture_video = aws_lambda_function.generate_lecture_video
  }
}

resource "aws_lambda_permission" "apigw" {
  for_each = local.lambda_functions

  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = each.value.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
