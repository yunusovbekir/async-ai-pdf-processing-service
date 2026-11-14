from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from app import main, redis_client


@pytest.fixture
async def fake_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "_client", client)
    yield client
    await client.aclose()


@pytest.fixture
async def client(fake_redis: fakeredis.aioredis.FakeRedis) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        yield c
