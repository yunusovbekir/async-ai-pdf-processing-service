# POST /documents

Upload 1..`MAX_FILES_PER_UPLOAD` PDFs as one batch and queue each for processing.

**Request** – `multipart/form-data`

| Field    | Type            | Required | Notes                                  |
|----------|-----------------|----------|----------------------------------------|
| `files`  | file (repeated) | yes      | PDFs, each ≤ `MAX_FILE_SIZE_MB`        |
| `parser` | string          | no       | `pypdf` (default), `llm`, or `gemini` (legacy alias of `llm`) |

```bash
curl -F files=@a.pdf -F files=@b.pdf -F parser=pypdf localhost:8000/documents
```

**Response `202`**

```json
{
  "batch_id": "9f1c...",
  "documents": [{"id": "3a7e...", "filename": "a.pdf", "status": "queued"}]
}
```

**Errors**

| Status | When                                                                 |
|--------|----------------------------------------------------------------------|
| 400    | Too many files, empty file, or file not starting with `%PDF-`        |
| 413    | A file exceeds `MAX_FILE_SIZE_MB` (wins over 400 if both occur)      |
| 422    | Invalid `parser` or no `files`                                       |
| 503    | Redis failure while creating records/enqueueing (saved files removed)|

Per-file validation errors (400/413) look like:

```json
{"detail": [{"filename": "b.pdf", "error": "not a PDF file (missing %PDF- header)"}]}
```

**Behavior**
- All files are validated before anything is persisted; if any is invalid the whole request is rejected and saved files are deleted.
- Each document and the batch get a uuid4 hex id.
- Records are created atomically (status `queued`), then one job per document is added to the `docs:jobs` stream.

Code: `backend/app/api/documents.py`. See [storage](../features/storage.md), [queue](../features/queue.md), [repository](../features/repository.md).
