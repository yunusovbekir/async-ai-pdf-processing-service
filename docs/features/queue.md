# Queue (`backend/app/queue.py`)

Redis Streams job queue.

| Item           | Value            |
|----------------|------------------|
| Stream         | `docs:jobs`      |
| Consumer group | `workers`        |
| Dead letters   | `docs:jobs:dead` |
| Entry fields   | `document_id`, `attempt` |

- `ensure_group(client)` runs on API startup: `XGROUP CREATE docs:jobs workers 0 MKSTREAM`, ignoring `BUSYGROUP` (idempotent).
- `enqueue(client, document_id, attempt=1)` does `XADD` with approximate `MAXLEN ~ 100000` and returns the entry id.

Jobs are consumed by the [worker](worker.md), which re-enqueues transient failures with `attempt+1` and writes exhausted jobs to `docs:jobs:dead` (fields `document_id`, `attempt`, `error`).
