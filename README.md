# NovaBuddy – AI-Powered Study Buddy

Serverless backend for the Amazon Nova AI Hackathon (Best Student App category).

Students upload lecture materials (PDFs, images) and NovaBuddy generates summaries,
quizzes, flashcards, key concepts, and an interactive Q&A chatbot — all powered by
Amazon Nova models via Bedrock.

## Architecture

- **Compute:** 7 AWS Lambda functions (Python 3.12)
- **API:** HTTP API Gateway with Cognito JWT authorizer
- **Auth:** Amazon Cognito User Pool (email + password)
- **Storage:** S3 (files) + DynamoDB single-table (metadata + AI outputs)
- **AI:** Amazon Nova Lite via Bedrock Converse API
- **IaC:** Terraform

## Prerequisites

1. **Terraform** >= 1.5 — [install](https://developer.hashicorp.com/terraform/install)
2. **AWS CLI** configured with credentials that have admin access (or scoped to the services above)
3. **Bedrock model access** — enable `amazon.nova-lite-v1:0` in the
   [Bedrock console](https://console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess)
   for `us-east-1`

## Deploy

```bash
cd terraform

# Copy the example and adjust if needed
cp terraform.tfvars.example terraform.tfvars

terraform init
terraform plan
terraform apply
```

Terraform outputs the values you need:

| Output                | Description                   |
|-----------------------|-------------------------------|
| `api_url`             | Base URL of the HTTP API      |
| `cognito_user_pool_id`| Cognito User Pool ID         |
| `cognito_client_id`   | Cognito App Client ID        |
| `s3_bucket_name`      | S3 uploads bucket name       |
| `dynamodb_table_name` | DynamoDB table name           |

## Terraform Variables

| Variable             | Default                                               | Description                                                                 |
|----------------------|--------------------------------------------------------|-----------------------------------------------------------------------------|
| `project_name`       | `novabuddy`                                           | Prefix for all AWS resource names                                           |
| `region`             | `us-east-1`                                           | AWS region (must support Nova models)                                       |
| `model_id`           | `amazon.nova-lite-v1:0`                               | Bedrock model ID for reasoning                                              |
| `embedding_model_id` | `amazon.nova-embed-multimodal-v1:0`                    | Bedrock model ID for embeddings (stretch goal)                              |
| `allowed_origins`    | `["https://main.d28f2w8xvnnyj5.amplifyapp.com"]`      | Frontend URLs for API Gateway CORS and Cognito callback/logout URLs         |

See `terraform/terraform.tfvars.example` for a ready-to-use config file. For local dev, add e.g. `"http://localhost:3000"` to `allowed_origins`.

## Create a Test User

```bash
# Replace <POOL_ID> and <CLIENT_ID> with Terraform outputs

# Sign up
aws cognito-idp sign-up \
  --client-id <CLIENT_ID> \
  --username you@example.com \
  --password YourPass123

# Confirm (admin shortcut — skips email verification)
aws cognito-idp admin-confirm-sign-up \
  --user-pool-id <POOL_ID> \
  --username you@example.com

# Get tokens
aws cognito-idp initiate-auth \
  --client-id <CLIENT_ID> \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=you@example.com,PASSWORD=YourPass123
```

Save the `IdToken` from the response — use it as the Bearer token for all API calls.

## API Reference

Base path: `<api_url>/api/v1`

All routes except `/health` require `Authorization: Bearer <IdToken>`.

### Health Check

```bash
curl <API_URL>/api/v1/health
```

### Upload a Lecture

```bash
# Step 1: Get presigned URL
curl -X POST <API_URL>/api/v1/upload/presigned \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"filename": "lecture1.pdf", "contentType": "application/pdf"}'

# Step 2: Upload file directly to S3 using the returned URL
curl -X PUT "<PRESIGNED_URL>" \
  -H "Content-Type: application/pdf" \
  --data-binary @lecture1.pdf
```

### Process a Lecture (generate study aids)

```bash
curl -X POST <API_URL>/api/v1/lectures/<LECTURE_ID>/process \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Machine Learning Week 3"}'
```

This triggers Nova to extract text, generate a summary (300-500 words),
8-12 quiz questions, and key concepts. Takes 30-90 seconds depending on file size.

### List Lectures

```bash
curl <API_URL>/api/v1/lectures \
  -H "Authorization: Bearer <TOKEN>"
```

### Get Lecture Details

```bash
curl <API_URL>/api/v1/lectures/<LECTURE_ID> \
  -H "Authorization: Bearer <TOKEN>"
```

### Chat about a Lecture

```bash
curl -X POST <API_URL>/api/v1/lectures/<LECTURE_ID>/chat \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain backpropagation in simple terms",
    "history": []
  }'
```

### Delete a Lecture

```bash
curl -X DELETE <API_URL>/api/v1/lectures/<LECTURE_ID> \
  -H "Authorization: Bearer <TOKEN>"
```

## Tear Down

```bash
cd terraform
terraform destroy
```

## Project Structure

```
├── terraform/
│   ├── main.tf                    # Provider, random suffix
│   ├── variables.tf               # Input variables (incl. allowed_origins)
│   ├── terraform.tfvars.example   # Example variable values
│   ├── outputs.tf                 # API URL, Cognito IDs, bucket name
│   ├── cognito.tf                 # User Pool + App Client (callback/logout URLs)
│   ├── storage.tf                 # S3 + DynamoDB
│   ├── api_gateway.tf             # HTTP API, JWT authorizer, CORS, routes
│   └── lambdas.tf                 # IAM, Lambda functions, Layer, permissions
├── lambdas/
│   ├── layer/python/shared/       # Shared utilities (Lambda Layer)
│   │   ├── response.py            # HTTP response helpers + @api_handler
│   │   └── bedrock.py             # Bedrock Converse API wrapper
│   ├── health/                    # GET  /health
│   ├── get_presigned/             # POST /upload/presigned
│   ├── process_lecture/           # POST /lectures/{id}/process
│   ├── list_lectures/             # GET  /lectures
│   ├── get_lecture/               # GET  /lectures/{id}
│   ├── chat_lecture/              # POST /lectures/{id}/chat
│   └── delete_lecture/            # DELETE /lectures/{id}
├── docs/
│   └── ARCHITECTURE.md            # AWS architecture diagram + data flows
├── .gitignore
├── PRD.md
└── README.md
```
