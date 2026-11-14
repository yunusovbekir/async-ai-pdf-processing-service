import asyncio
import logging
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024
PDF_MAGIC = b"%PDF-"


class InvalidUploadError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def upload_path(document_id: str) -> Path:
    """Return the on-disk path for a document id."""
    return Path(get_settings().UPLOAD_DIR) / f"{document_id}.pdf"


async def save_upload(file: UploadFile, document_id: str) -> Path:
    """Stream the upload to disk in chunks, enforcing size and PDF signature.

    Removes the partial file and raises InvalidUploadError on failure.
    """
    max_bytes = get_settings().MAX_FILE_SIZE_MB * 1024 * 1024
    path = upload_path(document_id)
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    handle = await asyncio.to_thread(path.open, "wb")
    total = 0
    try:
        while chunk := await file.read(CHUNK_SIZE):
            if total == 0 and not chunk.startswith(PDF_MAGIC):
                raise InvalidUploadError("not a PDF file (missing %PDF- header)")
            total += len(chunk)
            if total > max_bytes:
                raise InvalidUploadError(
                    f"file exceeds {get_settings().MAX_FILE_SIZE_MB} MB limit", 413
                )
            await asyncio.to_thread(handle.write, chunk)
        if total == 0:
            raise InvalidUploadError("file is empty")
    except BaseException:
        await asyncio.to_thread(handle.close)
        await delete_files([path])
        raise
    await asyncio.to_thread(handle.close)
    logger.info("upload saved document_id=%s bytes=%d", document_id, total)
    return path


async def delete_files(paths: list[Path]) -> None:
    """Delete the given files off the event loop, ignoring missing ones."""

    def _delete() -> None:
        for path in paths:
            path.unlink(missing_ok=True)

    await asyncio.to_thread(_delete)
