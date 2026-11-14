import pytest
from httpx import AsyncClient

from app import redis_client


async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_health_degraded_when_redis_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom() -> None:
        raise ConnectionError("down")

    monkeypatch.setattr(redis_client._client, "ping", boom)
    response = await client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
