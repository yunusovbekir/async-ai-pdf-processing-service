# GET /batches/{id}

Return a batch and all its documents (without pages, to stay light). Use it to poll overall progress.

```bash
curl localhost:8000/batches/9f1c...
```

**Response `200`**

```json
{
  "id": "9f1c...",
  "parser": "pypdf",
  "created_at": "2026-01-01T12:00:00+00:00",
  "documents": [
    {"id": "3a7e...", "batch_id": "9f1c...", "filename": "a.pdf", "parser": "pypdf",
     "status": "queued", "summary_status": "pending", "summary": null, "error": null,
     "page_count": null, "attempts": 0,
     "created_at": "...", "updated_at": "..."}
  ]
}
```

Documents keep upload order and have the same fields as [GET /documents/{id}](get-document.md) minus `pages`.

**Errors:** `404` if the batch is unknown or expired.
