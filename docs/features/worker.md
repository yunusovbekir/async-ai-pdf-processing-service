# Worker (`backend/app/worker/main.py`)

Run with `python -m app.worker.main` (compose service `worker`).

## Consuming
- Consumer name `hostname-pid` in group `workers` on stream `docs:jobs`.
- Loop: `XREADGROUP` (block 5s, count = free slots). At most `WORKER_CONCURRENCY` jobs run at once (semaphore); reading pauses while all slots are busy.
- `docker compose up --scale worker=N` runs N workers; the consumer group distributes entries between them.
- A readiness file `/tmp/worker-ready` is written while running (compose healthcheck).

## Pipeline per job
1. Unknown document -> dropped; `completed` document -> skipped (idempotency).
2. `attempts` = job attempt; status `parsing`; parse via `get_parser(doc.parser)` from `UPLOAD_DIR/{id}.pdf`.
3. Replace `doc:{id}:pages`, set `page_count` (and the "no text layer" note in `error` if all pages are empty).
4. Status `summarizing`; summary step (currently `summary_status=skipped`, hook for the Gemini summarizer).
5. Status `completed`; `XACK`.
Every status change is published on `batch:{id}:events`.

## Failures
- `ParserError` is permanent: status `failed` with `error`, `XACK`.
- Any other exception is transient: if `attempt < MAX_ATTEMPTS`, status goes back to `queued`, the job is re-enqueued with `attempt+1` and acked; otherwise status `failed`, the entry `{document_id, attempt, error}` is added to `docs:jobs:dead`, and acked.

## Crash recovery
A background task runs `XAUTOCLAIM` every `CLAIM_IDLE_MS/2` seconds (min 1s) for entries idle longer than `CLAIM_IDLE_MS` (left by crashed consumers) and processes them; entries already running locally are ignored.

## Shutdown
On SIGTERM/SIGINT the worker stops reading and claiming, waits for in-flight jobs, removes the readiness file and closes Redis (reads block up to 5s, so shutdown may take that long).
