import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app import gemini_client, repository
from app.worker.main import Consumer

FIXTURE = Path(__file__).parent / "fixtures" / "text.pdf"
UPLOADS = 20


async def test_concurrent_uploads_are_all_accepted_and_processed(
    client: AsyncClient, fake_redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Twenty simultaneous uploads are accepted and every document completes."""
    monkeypatch.setattr(gemini_client, "generate", AsyncMock(return_value="summary"))
    data = FIXTURE.read_bytes()

    responses = await asyncio.gather(
        *(
            client.post("/documents", files=[("files", (f"{i}.pdf", data, "application/pdf"))])
            for i in range(UPLOADS)
        )
    )
    assert {r.status_code for r in responses} == {202}
    ids = [r.json()["documents"][0]["id"] for r in responses]
    assert len(set(ids)) == UPLOADS
    assert await fake_redis.xlen("docs:jobs") == UPLOADS

    consumer = Consumer(fake_redis, "test-consumer", concurrency=4, claim_idle_ms=60_000)
    task = asyncio.create_task(consumer.run())
    try:
        for _ in range(200):
            docs = [await repository.get_document(fake_redis, i, with_pages=False) for i in ids]
            if all(d["status"] == "completed" for d in docs):
                break
            await asyncio.sleep(0.1)
    finally:
        consumer.stop.set()
        await asyncio.wait_for(task, timeout=10)

    assert all(d["status"] == "completed" and d["summary"] == "summary" for d in docs)
    assert (await fake_redis.xpending("docs:jobs", "workers"))["pending"] == 0
