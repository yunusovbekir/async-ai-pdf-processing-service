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

| Endpoint | Description | Details |
|----------|-------------|---------|
| `GET /health` | API + Redis health (`200` / `503`) | [doc](docs/api/health.md) |
| `POST /documents` | Upload PDFs, returns `202` with `batch_id` and document ids | [doc](docs/api/post-documents.md) |
| `GET /documents/{id}` | Status, error, summary, pages (`404` if unknown/expired) | [doc](docs/api/get-document.md) |
| `GET /batches/{id}` | Batch with its documents, without pages (`404`) | [doc](docs/api/get-batch.md) |

```bash
curl -F files=@a.pdf -F files=@b.pdf -F parser=pypdf localhost:8000/documents
# {"batch_id": "...", "documents": [{"id": "...", "filename": "a.pdf", "status": "queued"}, ...]}
curl localhost:8000/documents/<document_id>
curl localhost:8000/batches/<batch_id>
curl localhost:8000/health
```

Upload errors: `400` (non-PDF, empty, too many files; body `{"detail": [{"filename", "error"}]}`), `413` (file larger than `MAX_FILE_SIZE_MB`), `422` (invalid `parser` / no files), `503` (Redis failure while enqueueing). Any invalid file rejects the whole request and removes saved files.

## Parsers

`pypdf` (default) extracts text per page; `gemini` is accepted but not implemented yet (documents fail with a clear error). Encrypted, corrupted and zero-page PDFs fail with a user-facing error; PDFs without a text layer complete with the note "no text layer found; try the gemini parser". See [parsers](docs/features/parsers.md).

## Worker

`python -m app.worker.main` (compose service `worker`; scale with `docker compose up --scale worker=3`). Each worker is a consumer `hostname-pid` in group `workers`, processing up to `WORKER_CONCURRENCY` jobs concurrently.

Pipeline: skip if `completed` -> `parsing` -> parse per page -> store pages + `page_count` -> `summarizing` -> summary step (currently `summary_status=skipped`; hook for Gemini) -> `completed` -> `XACK`.

- `ParserError` is permanent: document `failed`, job acked.
- Other exceptions are transient: re-enqueued with `attempt+1` while `attempt < MAX_ATTEMPTS`; afterwards the document is `failed` and the job goes to `docs:jobs:dead`.
- `XAUTOCLAIM` takes over jobs idle longer than `CLAIM_IDLE_MS` (crashed consumers).
- SIGTERM/SIGINT: stop reading, finish in-flight jobs.

See [worker](docs/features/worker.md), [queue](docs/features/queue.md).

## Redis data model

| Key | Type | Content |
|-----|------|---------|
| `docs:jobs` | stream | fields `document_id`, `attempt`; group `workers` |
| `docs:jobs:dead` | stream | exhausted jobs (`document_id`, `attempt`, `error`) |
| `doc:{id}` | hash | id, batch_id, filename, parser, status (`queued\|parsing\|summarizing\|completed\|failed`), summary_status (`pending\|completed\|failed\|skipped`), summary, error, page_count, attempts, created_at, updated_at |
| `doc:{id}:pages` | list | JSON `{"page", "content"}` |
| `batch:{id}` / `batch:{id}:docs` | hash / list | id, parser, created_at / document ids |
| `batch:{id}:events` | pub/sub | JSON `{document_id, status}` on every status change |

All keys expire after `DATA_TTL_SECONDS`; uploaded files live in `UPLOAD_DIR/{document_id}.pdf`, never in Redis. See [repository](docs/features/repository.md), [storage](docs/features/storage.md).

## Configuration

All via environment (see `.env.example`).

| Variable | Default | Meaning |
|----------|---------|---------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection (compose overrides) |
| `UPLOAD_DIR` | `/data/uploads` | Shared upload volume (compose overrides) |
| `DATA_TTL_SECONDS` | `604800` | TTL for all Redis keys |
| `MAX_FILE_SIZE_MB` | `20` | Max size per file |
| `MAX_FILES_PER_UPLOAD` | `10` | Max files per request |
| `GEMINI_API_KEY` | empty | Gemini key (not used yet) |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Gemini model (not used yet) |
| `GEMINI_MAX_CONCURRENCY` | `2` | Gemini concurrency (not used yet) |
| `WORKER_CONCURRENCY` | `4` | Concurrent jobs per worker |
| `MAX_ATTEMPTS` | `3` | Attempts before dead-lettering |
| `CLAIM_IDLE_MS` | `60000` | Idle time before a pending job is reclaimed |
| `LOG_LEVEL` | `INFO` | Logging level |

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
- The `gemini` parser and summarization are not implemented yet; the summary step is skipped (`summary_status=skipped`).
- A missing document hash (expired TTL) makes the worker drop the job.
