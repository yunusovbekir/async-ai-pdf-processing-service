import os
import time
from pathlib import Path

import pytest

from app.config import get_settings
from app.storage import cleanup_expired_uploads, upload_path


def _make(document_id: str, age_seconds: int) -> Path:
    path = upload_path(document_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-")
    mtime = time.time() - age_seconds
    os.utime(path, (mtime, mtime))
    return path


async def test_old_files_removed_and_fresh_kept() -> None:
    ttl = get_settings().UPLOAD_TTL_SECONDS
    old = _make("old", ttl + 60)
    fresh = _make("fresh", ttl - 3600)

    assert await cleanup_expired_uploads() == 1
    assert not old.exists()
    assert fresh.exists()


async def test_custom_max_age_ignores_non_pdf() -> None:
    old = _make("a", 120)
    other = old.parent / "notes.txt"
    other.write_text("x")
    os.utime(other, (0, 0))

    assert await cleanup_expired_uploads(60) == 1
    assert not old.exists()
    assert other.exists()


async def test_missing_directory_is_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(get_settings(), "UPLOAD_DIR", str(tmp_path / "nope"))
    assert await cleanup_expired_uploads() == 0
