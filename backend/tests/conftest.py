from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from app import main, queue, redis_client
from app.config import get_settings


@pytest.fixture
async def fake_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "_client", client)
    await queue.ensure_group(client)
    yield client
    await client.aclose()


@pytest.fixture
async def client(fake_redis: fakeredis.aioredis.FakeRedis) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "1")
    monkeypatch.setenv("MAX_FILES_PER_UPLOAD", "3")
    get_settings.cache_clear()
    yield tmp_path / "uploads"
    get_settings.cache_clear()
