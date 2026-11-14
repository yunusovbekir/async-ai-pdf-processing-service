# Storage (`backend/app/storage.py`)

Saves uploaded PDFs to the shared volume at `UPLOAD_DIR/{document_id}.pdf`. File bytes are never stored in Redis.

- `save_upload(file, document_id)` streams the upload in 1 MiB chunks (never reads the whole file into memory) and enforces:
  - first bytes are `%PDF-`
  - total size ≤ `MAX_FILE_SIZE_MB` (checked while streaming)
  - file is not empty
  
  On failure the partial file is removed and `InvalidUploadError(message, status_code)` is raised (`400`, or `413` for size).
- `upload_path(document_id)` returns the path; the worker uses it to read the file.
- `delete_files(paths)` removes files, ignoring missing ones.
- `cleanup_expired_uploads(max_age_seconds=None)` deletes `*.pdf` files older than `UPLOAD_TTL_SECONDS` (by mtime) and returns the count; tolerant of a missing directory and of files deleted concurrently. The worker runs it at startup and every `UPLOAD_CLEANUP_INTERVAL_SECONDS`.

All file I/O runs through `asyncio.to_thread`, so the event loop is never blocked. `UPLOAD_DIR` is created on demand.
