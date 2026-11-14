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

The worker is not implemented yet: jobs stay in the stream.

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
- Empty `error`/`summary` are returned as `null`.
