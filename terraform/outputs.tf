output "api_url" {
  description = "Base URL of the HTTP API"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  description = "Cognito App Client ID"
  value       = aws_cognito_user_pool_client.main.id
}

output "s3_bucket_name" {
  description = "S3 uploads bucket name (lecture files)"
  value       = aws_s3_bucket.uploads.id
}

output "s3_generated_bucket_name" {
  description = "S3 generated bucket name (summary audio outputs)"
  value       = aws_s3_bucket.generated.id
}

output "dynamodb_table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.lectures.name
}
