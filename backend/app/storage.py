"""Upload storage on the shared volume."""

import asyncio
import logging
import time
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024
PDF_MAGIC = b"%PDF-"


class InvalidUploadError(Exception):
    """An uploaded file failed validation.

    Attributes:
        message: Human-readable reason.
        status_code: Suggested HTTP status code.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        """Create the error with a message and suggested HTTP status."""
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def upload_path(document_id: str) -> Path:
    """Return the on-disk path for a document.

    Args:
        document_id: Document identifier.

    Returns:
        Path of the form UPLOAD_DIR/{document_id}.pdf.
    """
    return Path(get_settings().UPLOAD_DIR) / f"{document_id}.pdf"


async def save_upload(file: UploadFile, document_id: str) -> Path:
    """Stream the upload to disk in chunks, enforcing size and PDF signature.

    Args:
        file: Uploaded file.
        document_id: Identifier used for the stored file name.

    Returns:
        Path of the saved file.

    Raises:
        InvalidUploadError: If the file is empty, not a PDF or too large.
            The partial file is removed.
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
    """Delete files off the event loop, ignoring missing ones.

    Args:
        paths: Files to delete.
    """

    def _delete() -> None:
        for path in paths:
            path.unlink(missing_ok=True)

    await asyncio.to_thread(_delete)


async def cleanup_expired_uploads(max_age_seconds: int | None = None) -> int:
    """Delete stored PDFs whose last modification is older than the retention period.

    Safe to run concurrently from several workers: a file removed by another process
    in the meantime is ignored. A missing upload directory is not an error.

    Args:
        max_age_seconds: Retention in seconds; defaults to UPLOAD_TTL_SECONDS.

    Returns:
        Number of files deleted by this call.
    """
    settings = get_settings()
    max_age = settings.UPLOAD_TTL_SECONDS if max_age_seconds is None else max_age_seconds
    directory = Path(settings.UPLOAD_DIR)

    def _cleanup() -> int:
        cutoff = time.time() - max_age
        deleted = 0
        try:
            entries = list(directory.glob("*.pdf"))
        except OSError:
            logger.exception("upload cleanup cannot list directory=%s", directory)
            return 0
        for path in entries:
            try:
                if path.stat().st_mtime >= cutoff:
                    continue
                path.unlink()
                deleted += 1
            except FileNotFoundError:
                continue
            except OSError:
                logger.exception("upload cleanup failed path=%s", path)
        return deleted

    deleted = await asyncio.to_thread(_cleanup)
    if deleted:
        logger.info("upload cleanup deleted=%d max_age_seconds=%d", deleted, max_age)
    return deleted
