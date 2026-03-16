# Nova Buddy — Frontend Integration Guide

Encoding (Content-Type) for S3 upload and full flow from auth to chat.

---

## 1. Encoding & Content-Type for S3 Presigned Upload

The presigned URL is signed with a specific `Content-Type` based on the file extension. **You must send the same Content-Type** when uploading, or S3 will reject with `SignatureDoesNotMatch`.

### Option A: Use filename → derive Content-Type (match backend)

```typescript
const EXT_TO_MIME: Record<string, string> = {
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
};

function getContentType(filename: string): string {
  const ext = filename.toLowerCase().slice(filename.lastIndexOf("."));
  return EXT_TO_MIME[ext] ?? "application/octet-stream";
}
```

### Option B: Backend returns `contentType` (if we add it)

If `get_presigned` returns `{ url, lectureId, contentType }`, use that directly when uploading.

### PUT to presigned URL — correct encoding

```typescript
async function uploadToPresignedUrl(
  file: File,
  presignedUrl: string,
  filename: string
): Promise<void> {
  const contentType = getContentType(filename);

  const res = await fetch(presignedUrl, {
    method: "PUT",
    headers: {
      "Content-Type": contentType,
      // Do NOT send Authorization — presigned URL has auth in the query string
    },
    body: file, // raw File blob — leave as-is, do NOT stringify
  });

  if (!res.ok) {
    throw new Error(`Upload failed: ${res.status}`);
  }
}
```

**Important:**
- `body` = raw `File` object (or `Blob`). No Base64, no JSON.
- `Content-Type` must match what the backend used when generating the presigned URL.
- Do **not** send `Authorization` to S3 — the presigned URL handles auth.

---

## 2. Full Frontend Flow

### High-level flow

```
[Login] → [Dashboard / Lecture List] → [Upload] → [Process] → [View / Chat]
                ↑                                                      │
                └──────────────────── [List Lectures] ←─────────────────┘
```

---

### Step-by-step flow

#### 1. User logs in (Cognito)

- Use Amplify `signIn` or Hosted UI
- Store access token (Amplify handles this)
- Redirect to `/dashboard` or `/`

#### 2. Dashboard — list lectures

```
GET /api/v1/lectures
Authorization: Bearer <accessToken>
```

**Response:**
```json
[
  {
    "lectureId": "...",
    "title": "lecture.pdf",
    "contentType": "application/pdf",
    "uploadTimestamp": "2026-03-16T16:11:29.957777Z",
    "hasSummary": true
  }
]
```

- Show list of lectures
- `hasSummary: true` → ready to view / chat
- `hasSummary: false` → show "Processing..." or "Process" button

#### 3. Upload a new lecture

**3a. Request presigned URL**

```typescript
const res = await apiFetch("/api/v1/upload/presigned", {
  method: "POST",
  body: JSON.stringify({ filename: file.name }),
});

const { url, lectureId } = await res.json();
```

**3b. Upload file to S3**

```typescript
await uploadToPresignedUrl(file, url, file.name);
```

**3c. Immediately call process (or let user trigger it)**

```typescript
await apiFetch(`/api/v1/lectures/${lectureId}/process`, {
  method: "POST",
  body: JSON.stringify({ title: file.name }), // optional
});
```

- Processing can take 30–60+ seconds
- Poll `GET /api/v1/lectures/{lectureId}` until `summary` exists, or show a loading state

#### 4. View lecture / chat

- User clicks a lecture from the list
- `GET /api/v1/lectures/{lectureId}` → get `summary`, `quizJson`, `keyConcepts`, `processedText`
- Parse `quizJson`: `JSON.parse(lecture.quizJson)` → array of quiz items
- Render `summary` and `keyConcepts` as Markdown

**Chat:**

```typescript
const res = await apiFetch(`/api/v1/lectures/${lectureId}/chat`, {
  method: "POST",
  body: JSON.stringify({
    message: "What are the main points?",
    history: conversationHistory, // optional, last 10 messages
  }),
});

const { reply } = await res.json();
```

#### 5. Delete lecture

```typescript
await apiFetch(`/api/v1/lectures/${lectureId}`, {
  method: "DELETE",
});
```

---

## 3. API client helper (with auth)

```typescript
import { fetchAuthSession } from "aws-amplify/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;

export async function apiFetch(
  path: string,
  init: RequestInit = {}
): Promise<Response> {
  const session = await fetchAuthSession();
  const token = session.tokens?.accessToken?.toString();

  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
    body: init.body ?? undefined,
  });
}
```

---

## 4. Suggested UI flow (screens)

| Screen | Actions |
|--------|---------|
| **Auth** | Sign in / Sign up |
| **Dashboard** | List lectures, "Upload" button |
| **Upload modal** | File picker → upload → "Processing..." |
| **Lecture list item** | Title, status (Ready / Processing), Open, Delete |
| **Lecture detail** | Summary, Key concepts, Quiz, Chat tab |
| **Chat** | Message input, history, reply |

---

## 5. Processing status

The `/process` endpoint is synchronous — it blocks until done. For long runs:

1. Call `POST /lectures/{id}/process` in the background (e.g. `fetch` without awaiting UI)
2. Poll `GET /lectures/{id}` until `summary` is present
3. Or show "Processing..." and refresh the list every few seconds

---

## 6. Quiz JSON structure (for rendering)

```typescript
type QuizItem =
  | {
      type: "mcq";
      question: string;
      options: string[];
      answer: string;
      explanation: string;
    }
  | {
      type: "short_answer";
      question: string;
      answer: string;
      explanation: string;
    };

const quiz = JSON.parse(lecture.quizJson) as QuizItem[];
```

---

## 7. Quick reference — file extensions & Content-Type

| Extension | Content-Type |
|-----------|--------------|
| `.pdf` | `application/pdf` |
| `.mp4` | `video/mp4` |
| `.mp3` | `audio/mpeg` |
| `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `.txt` | `text/plain` |
| Other | `application/octet-stream` |
