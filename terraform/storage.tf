# ── S3 Bucket ──────────────────────────────────────────────────────

resource "aws_s3_bucket" "uploads" {
  bucket        = "${local.name_prefix}-uploads"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_cors_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "GET"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}

# Trigger auto-processing Lambda when a new object is created in the uploads bucket
resource "aws_s3_bucket_notification" "uploads_process_lecture" {
  bucket = aws_s3_bucket.uploads.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.process_lecture.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [
    aws_lambda_permission.s3_invoke_process_lecture,
  ]
}

# ── Generated Content Bucket (summary audio, video) ─────────────────

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "generated" {
  bucket        = "${local.name_prefix}-generated"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "generated" {
  bucket = aws_s3_bucket.generated.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "generated" {
  bucket = aws_s3_bucket.generated.id

  block_public_acls       = true
  block_public_policy      = true
  ignore_public_acls      = true
  restrict_public_buckets  = true
}

resource "aws_s3_bucket_cors_configuration" "generated" {
  bucket = aws_s3_bucket.generated.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET"]
    allowed_origins = ["*"]
    max_age_seconds = 3600
  }
}

# Allow Bedrock to write Nova Reel video output to generated bucket
resource "aws_s3_bucket_policy" "generated_bedrock" {
  bucket = aws_s3_bucket.generated.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowBedrockNovaReelWrite"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.generated.arn}/*"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:*"
          }
        }
      }
    ]
  })
}

# ── DynamoDB Table ─────────────────────────────────────────────────

resource "aws_dynamodb_table" "lectures" {
  name         = "${local.name_prefix}-lectures"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "lecture_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "lecture_id"
    type = "S"
  }
}
