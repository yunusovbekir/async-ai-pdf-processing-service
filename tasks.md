
## MUST parts (one PR = one prompt)

### PR 1 – Project scaffold & Docker Compose

```
Task: scaffold the project. No business logic yet.

Scope:
- Repo layout per the system prompt. backend/pyproject.toml managed by uv with deps: fastapi, uvicorn[standard], redis, pydantic-settings, python-multipart, pypdf, google-genai, tenacity; dev deps: pytest, pytest-asyncio, httpx, fakeredis, ruff.
- app/config.py: Settings with REDIS_URL, UPLOAD_DIR, DATA_TTL_SECONDS (7 days), MAX_FILE_SIZE_MB (20), MAX_FILES_PER_UPLOAD (10), GEMINI_API_KEY, GEMINI_MODEL (strip whitespace), GEMINI_MAX_CONCURRENCY (2), WORKER_CONCURRENCY (4), MAX_ATTEMPTS (3), CLAIM_IDLE_MS (60000), LOG_LEVEL.
- app/redis_client.py: lazily created shared redis.asyncio client (decode_responses=True), closed on shutdown.
- app/main.py: FastAPI app with lifespan, logging setup, GET /health that pings Redis (200 ok / 503 degraded).
- app/worker/main.py: placeholder entrypoint that connects to Redis, logs "worker started" and waits for SIGTERM gracefully.
- backend/Dockerfile: python:3.12-slim, uv, non-root user, layer caching for deps.
- docker-compose.yml: redis:7-alpine with appendonly yes + healthcheck + volume; api (port 8000) and worker built from the same image, depends_on redis service_healthy, shared "uploads" volume, env_file .env; api healthcheck on /health.
- .env.example, .gitignore, .dockerignore (exclude .venv, node_modules, __pycache__, .env).
- Minimal README: how to run (docker compose up --build), how to run tests.
- Test: /health returns 200 with fakeredis.

Done when: `docker compose up --build` starts all 3 services healthy, `curl localhost:8000/health` returns ok, ruff and pytest pass.
```

### PR 2 – Upload API, storage, enqueue to Redis Streams

```
Task: implement document upload and read endpoints. The worker is not implemented yet; jobs just sit in the stream.

Scope:
- app/schemas.py: ParserType enum (pypdf, gemini), DocumentStatus, SummaryStatus enums; response models for upload, document, batch.
- app/storage.py: stream the upload to UPLOAD_DIR/{document_id}.pdf in chunks (no full read into memory), enforce MAX_FILE_SIZE_MB while streaming, verify the file starts with "%PDF-". Run file I/O off the event loop.
- app/repository.py: functions to create batch + documents, get document (with pages), get batch (with its documents), update status (also publishes to "batch:{id}:events"). Use pipelines/transactions; apply TTL.
- app/queue.py: ensure stream + consumer group exist on startup (XGROUP CREATE ... MKSTREAM, ignore BUSYGROUP); enqueue(document_id, attempt=1) via XADD with approximate MAXLEN.
- Endpoints (api/documents.py):
  - POST /documents: multipart "files" (1..MAX_FILES_PER_UPLOAD) + form field "parser" (default pypdf). Validate everything first; if any file is invalid, reject the whole request with a clear per-file error and clean up saved files. On success create records (status queued), enqueue each document, return 202 with batch_id and documents [{id, filename, status}].
  - GET /documents/{id}: metadata, status, error, summary, pages. 404 if unknown.
  - GET /batches/{id}: batch + all its documents (without pages, to keep it light). 404 if unknown.
- IDs: uuid4 hex.
- Tests (fakeredis): happy path with 2 files, non-PDF rejected, oversized rejected, too many files, invalid parser -> 422, stream contains one entry per document, GET 404s.

Out of scope: processing, Gemini, SSE.
```

### PR 3 – Worker: Redis Streams consumer + PyPDF parser

```
Task: implement the background worker and the PyPDF parser.

Scope:
- parsers/base.py: Parser protocol: async parse(path: Path) -> list[PageContent]; ParserError for user-facing failures; get_parser(ParserType) registry.
- parsers/pypdf_parser.py: per-page text extraction via asyncio.to_thread. Handle: encrypted PDF (try empty password, else ParserError "encrypted PDF not supported"), corrupted/unreadable PDF -> ParserError, zero pages -> ParserError. If all pages return empty text, keep the pages but set error note "no text layer found; try the gemini parser" (document still completes).
- worker/main.py:
  - Consumer name = hostname-pid. Loop XREADGROUP (block 5s, count=WORKER_CONCURRENCY) and process messages concurrently, bounded by a semaphore.
  - Pipeline per document: skip if already completed (idempotency) -> status parsing -> parse -> store pages + page_count -> status summarizing -> summary step (for now: set summary_status=skipped, a hook for PR 4) -> status completed -> XACK.
  - Failures: ParserError = permanent -> status failed with error, XACK. Other exceptions = transient -> if attempt < MAX_ATTEMPTS re-enqueue with attempt+1 and XACK, else mark failed, XADD to "docs:jobs:dead", XACK.
  - Background task: periodically XAUTOCLAIM messages idle > CLAIM_IDLE_MS (crashed consumers) and process them.
  - Graceful shutdown on SIGTERM: stop reading, finish in-flight jobs.
- Ensure compose worker command runs it and `docker compose up --scale worker=3` works.
- Tests: commit 2 small fixture PDFs (text PDF, blank/no-text PDF) plus a corrupted file; test parser per-page output; test worker processes a job end to end on fakeredis (status transitions, pages stored, XACK), permanent failure, and transient retry -> dead letter after MAX_ATTEMPTS.

Out of scope: Gemini.
```

### PR 4 – Gemini client & summarization

```
Task: add Gemini-based summarization of each parsed document.

Scope:
- app/gemini_client.py: single async google-genai client (client.aio) built from settings; a global asyncio.Semaphore(GEMINI_MAX_CONCURRENCY); generate helper with tenacity retries (exponential backoff + jitter) on 429/5xx/timeouts only; request timeout. Raise a clear error if GEMINI_API_KEY is missing.
- app/summarizer.py: summarize(pages) -> str. Join page contents with page markers, truncate to a configurable SUMMARY_MAX_INPUT_CHARS, prompt for a concise markdown summary (short overview + key points), language = document language. Return "" without calling the API if the text is empty.
- Worker: replace the summary hook. On success set summary + summary_status=completed. Summary failure must NOT fail the document: keep pages, set summary_status=failed and store the error, status completed. Empty text -> summary_status=skipped.
- Tests with mocked client: summary stored, retry on 429 then success, summary failure keeps document completed with pages, empty text skips the API call.
- README: how to get a free Gemini API key, env vars, free-tier rate-limit note.
```

### PR 5 – Gemini parser (PDF -> markdown, per page)

```
Task: implement the "gemini" parser choice.

Scope:
- parsers/gemini_parser.py: split the PDF into single-page PDFs with pypdf (in a thread), send each page as Part.from_bytes(mime_type="application/pdf") with a prompt: "convert this page to clean GitHub-flavored markdown, preserve headings/lists/tables, describe images and charts briefly in italics, output only markdown". Run pages concurrently through the shared Gemini semaphore/retry helper; keep page order.
- Reuse pypdf_parser's validation for encrypted/corrupted/empty PDFs (extract shared helper).
- A single page that keeps failing after retries is a transient error for the whole document (worker retry policy applies). Missing API key -> ParserError with a clear message.
- Register in get_parser; POST /documents accepts parser=gemini.
- Tests with mocked client: page order preserved, per-page calls, failure propagates as expected.
- README: describe both parsers and when to use which (scanned PDFs -> gemini).
```

### PR 6 – Hardening, demo, docs

```
Task: polish for review. No new features.

Scope:
- scripts/demo.sh: upload 2 sample public PDFs with curl (one per parser), poll GET /batches/{id} until all docs are completed/failed, print summaries. Add sample PDFs under samples/ (public domain/small).
- Concurrency check: a test or script that fires ~20 concurrent uploads and confirms all are accepted and processed.
- Review error responses and logs for consistency; make sure no blocking calls exist in async code.
- README final: overview, architecture diagram (mermaid: client -> api -> redis stream -> workers -> redis -> polling/SSE), API reference with curl examples, Redis data model, retry/failure semantics, scaling workers, config table, Assumptions (no auth; UUIDs act as unguessable ids; GPT-5 Mini not implemented unless PR 8 done), Trade-offs, Future work (auth/multi-tenancy, PII masking, virus scanning, object storage instead of volume, metrics).
- Make sure `git archive`/zip excludes .venv, node_modules, .env.
```

---

## Nice-to-have (prompts later)
- PR 7 – SSE endpoint `GET /batches/{id}/events` (Redis Pub/Sub + initial snapshot, heartbeat)
- PR 8 – GPT-5 Mini parser (OCR), behind `OPENAI_API_KEY`
- PR 9 – React/Vite frontend: multi-file upload, parser select, live status via SSE (polling fallback), per-page view + summary
