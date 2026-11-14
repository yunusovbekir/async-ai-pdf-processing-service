# GET /documents/{id}

Return one document's metadata, status, summary and parsed pages.

```bash
curl localhost:8000/documents/3a7e...
```

**Response `200`**

```json
{
  "id": "3a7e...",
  "batch_id": "9f1c...",
  "filename": "a.pdf",
  "parser": "pypdf",
  "status": "queued",
  "summary_status": "pending",
  "summary": null,
  "error": null,
  "page_count": null,
  "attempts": 0,
  "created_at": "2026-01-01T12:00:00+00:00",
  "updated_at": "2026-01-01T12:00:00+00:00",
  "pages": [{"page": 1, "content": "..."}]
}
```

- `status`: `queued | parsing | summarizing | completed | failed`
- `summary_status`: `pending | completed | failed | skipped`
- `summary`, `error`, `page_count` are `null` until set; `pages` is `[]` until parsed.
- Timestamps are ISO 8601 UTC.

**Errors:** `404` if the document is unknown or expired (TTL `DATA_TTL_SECONDS`).

Code: `backend/app/api/documents.py`, models in `backend/app/schemas.py`.
