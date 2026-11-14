# Async PDF processing service

Upload PDFs, parse them per page (pypdf or Gemini) and summarize with Gemini. FastAPI + Redis Streams worker.

## Run

```bash
cp .env.example .env   # set GEMINI_API_KEY when needed
docker compose up --build
curl localhost:8000/health
```

Services: `api` (port 8000), `worker`, `redis`.

## API

- `POST /documents` – multipart `files` (1..`MAX_FILES_PER_UPLOAD`) and form field `parser` (`pypdf` default | `gemini`). Files are streamed to `UPLOAD_DIR/{document_id}.pdf`, checked for the `%PDF-` header and `MAX_FILE_SIZE_MB`. Returns `202 {batch_id, documents: [{id, filename, status}]}` and enqueues one job per document on the `docs:jobs` stream. Errors: `400` (non-PDF, empty, too many files; body `{"detail": [{"filename", "error"}]}`), `413` (file too large), `422` (invalid parser / no files). Any invalid file rejects the whole request and removes saved files.
- `GET /documents/{id}` – metadata, status, error, summary and pages (`404` if unknown).
- `GET /batches/{id}` – batch with all its documents, without pages (`404` if unknown).

## Worker

`python -m app.worker.main` (compose service `worker`; scale with `docker compose up --scale worker=3`). Each worker is a consumer named `hostname-pid` in group `workers`: it reads up to `WORKER_CONCURRENCY` jobs (`XREADGROUP`, block 5s) and processes them concurrently.

Pipeline per document: skip if already `completed` → `parsing` → parse (pypdf, per page) → store pages + `page_count` → `summarizing` → summary step (currently sets `summary_status=skipped`; hook for Gemini) → `completed` → `XACK`.

- `ParserError` (encrypted, corrupted or zero-page PDF) is permanent: document `failed` with `error`, job acked.
- Any other exception is transient: re-enqueued with `attempt+1` while `attempt < MAX_ATTEMPTS`; afterwards the document is `failed`, the job is added to `docs:jobs:dead` and acked.
- A background task `XAUTOCLAIM`s jobs idle longer than `CLAIM_IDLE_MS` (crashed consumers) and processes them.
- On SIGTERM/SIGINT the worker stops reading and finishes in-flight jobs.
- If a PDF has no extractable text, pages are kept (empty) and the document completes with `error` = "no text layer found; try the gemini parser".

Details: [POST /documents](docs/api/post-documents.md), [GET /documents/{id}](docs/api/get-document.md), [GET /batches/{id}](docs/api/get-batch.md); features: [storage](docs/features/storage.md), [queue](docs/features/queue.md), [repository](docs/features/repository.md).

## Tests

```bash
cd backend
uv sync
uv run ruff check .
uv run pytest
```

## Assumptions

- `.env` is required by compose; `REDIS_URL` and `UPLOAD_DIR` are overridden in compose for container paths.
- Upload validation errors use `413` if any file is oversized, otherwise `400`; too many files is `400`.
- A password-protected PDF is only supported if it opens with an empty password.
- A missing upload file is treated as a transient error (retried, then dead-lettered).
- Empty `error`/`summary` are returned as `null`.
