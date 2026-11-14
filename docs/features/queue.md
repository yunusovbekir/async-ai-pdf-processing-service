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

The worker is not implemented yet; entries stay pending in the stream until it is.
