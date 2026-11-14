# Repository & Redis data model (`backend/app/repository.py`)

All keys expire after `DATA_TTL_SECONDS`. Empty strings in hashes are returned as `null`.

| Key                      | Type    | Content                                                                                   |
|--------------------------|---------|-------------------------------------------------------------------------------------------|
| `doc:{id}`               | hash    | id, batch_id, filename, parser, status, summary_status, summary, error, page_count, attempts, created_at, updated_at |
| `doc:{id}:pages`         | list    | JSON `{"page": int (1-based), "content": str}`                                            |
| `batch:{id}`             | hash    | id, parser, created_at                                                                    |
| `batch:{id}:docs`        | list    | document ids in upload order                                                              |
| `batch:{id}:events`      | pub/sub | JSON `{"document_id", "status"}` on every status change                                   |

Functions
- `create_batch(client, batch_id, parser, documents)` – one transactional pipeline creating the batch and its documents (`status=queued`, `summary_status=pending`) with TTL.
- `get_document(client, id, with_pages=True)` – document dict or `None`.
- `get_batch(client, id)` – batch dict with `documents` (no pages) or `None`.
- `update_status(client, id, status, **fields)` – sets status plus extra fields, refreshes `updated_at` and TTL, and publishes the event, all in one transaction. Used by the worker (not yet implemented).

Enums (`DocumentStatus`, `SummaryStatus`, `ParserType`) and response models live in `backend/app/schemas.py`.
