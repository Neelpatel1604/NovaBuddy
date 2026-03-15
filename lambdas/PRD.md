# StudyNova – AI-Powered Study Buddy  
**Amazon Nova AI Hackathon – Best Student App Category**  

**PRD Version:** 1.0 (MVP)  
**Date:** March 14, 2026  
**Status:** Ready for implementation  
**Target Submission:** Amazon Nova AI Hackathon (deadline March 16, 2026)  
**Infrastructure as Code:** Terraform (AWS serverless)  
**Core Models Used:** amazon.nova-2-lite-v1:0 + amazon.nova-2-multimodal-embeddings-v1:0 (via Amazon Bedrock)  

## 1. Project Overview

**StudyNova** is an intelligent, multimodal study companion that helps students transform lecture materials (PDFs, slides, images, short videos/audio) into actionable study aids: summaries, quizzes, flashcards, key concepts, and interactive Q&A — all powered by Amazon Nova models.

**Goal for Hackathon:**  
Build a clean, functional MVP backend that demonstrates strong usage of Nova 2 Lite reasoning + multimodal capabilities, while being secure, scalable, and easy to connect to a simple frontend (React/Next.js/Streamlit/etc.).

**Why this wins Best Student App:**  
- Directly solves real student problems (lecture overload, poor retention, time pressure)  
- Measurable value: faster review, better understanding, personalized learning  
- Clear Nova integration (multimodal input → reasoning → output)  
- Social good angle for bonus blog post ($200 AWS credits)

## 2. Functional Requirements

### Authentication
- Amazon Cognito User Pool (email + password)  
- JWT Bearer tokens for all protected API endpoints  
- No social login for MVP

### Lecture Workflow
1. **Upload**  
   - Frontend requests presigned S3 PUT URL  
   - Student uploads file directly to S3 (bypasses API Gateway size limit)  
   - Supported: PDF, images (jpg/png), short video/audio (<~100 MB for MVP)

2. **Processing**  
   - Trigger Nova 2 Lite to:  
     - Extract/summarize content (300–500 word summary)  
     - Generate 8–12 quiz questions (mix MCQ + short answer)  
     - Extract key concepts / glossary terms  
   - Optional stretch: Generate multimodal embeddings per major section for future semantic search

3. **Storage**  
   - Original file → private S3 bucket  
   - Metadata + AI outputs → DynamoDB single table

4. **Chat / Q&A**  
   - Student asks natural-language questions about the lecture  
   - Full lecture text/context + conversation history sent to Nova 2 Lite every request  
   - Returns helpful, accurate, cited responses

### Data Model (DynamoDB – single table)
- Table name: `studynova-lectures`  
- Billing: PAY_PER_REQUEST  
- Partition key: `user_id` (Cognito sub – string)  
- Sort key: `lecture_id` (UUID – string)  
- Attributes:
  - `title`                 (string)
  - `s3_key`                (string)
  - `content_type`          (string – e.g. "application/pdf")
  - `upload_timestamp`      (ISO string)
  - `summary`               (string – markdown)
  - `quiz_json`             (string – JSON array of questions)
  - `key_concepts`          (string – markdown list)
  - `processed_text`        (string – full extracted content for chat)
  - `embeddings`            (optional – JSON array, stretch goal)

## 3. API Specification (REST – HTTP API Gateway)

**Base Path:** `/api/v1`  
**Auth:** Cognito JWT Authorizer on all routes except `/health`  
**CORS:** Enabled (`*` for dev, tighten for prod)

| Method | Path                                | Lambda              | Description                                      | Request Body Example                              | Response Example                                   |
|--------|-------------------------------------|---------------------|--------------------------------------------------|---------------------------------------------------|----------------------------------------------------|
| POST   | `/upload/presigned`                 | get-presigned       | Get S3 presigned upload URL                      | `{ "filename": "lec1.pdf", "contentType": "application/pdf" }` | `{ "url": "...", "lectureId": "uuid-v4" }`        |
| POST   | `/lectures/{lectureId}/process`     | process-lecture     | Run Nova processing on uploaded file             | `{ "title": "Machine Learning Week 3" }` (optional) | `{ "status": "completed", "summary": "...", ... }` |
| GET    | `/lectures`                         | list-lectures       | List all user's lectures                         | —                                                 | Array of lecture summaries                         |
| GET    | `/lectures/{lectureId}`             | get-lecture         | Get full lecture details + AI outputs            | —                                                 | Full lecture object                                |
| POST   | `/lectures/{lectureId}/chat`        | chat-lecture        | Ask question about this lecture                  | `{ "message": "Explain backpropagation", "history": [...] }` | `{ "reply": "..." }`                               |
| DELETE | `/lectures/{lectureId}`             | delete-lecture      | Delete lecture + S3 object                       | —                                                 | `{ "deleted": true }`                              |
| GET    | `/health`                           | health              | Public health check                              | —                                                 | `{ "status": "healthy" }`                          |

## 4. Non-Functional Requirements

- **Architecture:** 100% serverless (Lambda + API Gateway + Cognito + S3 + DynamoDB + Bedrock)  
- **Region:** us-east-1 (Nova models available here)  
- **Cost target:** <$1–2 for entire hackathon testing  
- **Security:**  
  - Least-privilege IAM roles  
  - Private S3 buckets  
  - Cognito authorizer only  
  - No public endpoints  
- **Timeouts:** 120–300 seconds for Nova calls (Lambda configurable)  
- **Logging & Observability:** CloudWatch Logs + X-Ray tracing  
- **Environment variables (Lambda):**  
  - `BEDROCK_REGION=us-east-1`  
  - `MODEL_ID=amazon.nova-2-lite-v1:0`  
  - `EMBEDDING_MODEL_ID=amazon.nova-2-multimodal-embeddings-v1:0`  
  - `UPLOAD_BUCKET_NAME=studynova-uploads-...`  
  - `DYNAMODB_TABLE=studynova-lectures`

## 5. Terraform Structure (Recommended)
