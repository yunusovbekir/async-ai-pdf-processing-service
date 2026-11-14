import asyncio
import json
from collections.abc import AsyncIterator

import fakeredis.aioredis
from httpx import AsyncClient

from app import repository
from app.api.events import batch_event_stream
from app.schemas import DocumentStatus, ParserType


async def _never() -> bool:
    return False


async def _make_batch(client: fakeredis.aioredis.FakeRedis, n: int = 2) -> tuple[str, list[str]]:
    ids = [f"d{i}" for i in range(n)]
    await repository.create_batch(client, "b1", ParserType.pypdf, [(i, f"{i}.pdf") for i in ids])
    return "b1", ids


def _parse(frame: str) -> tuple[str, dict]:
    lines = frame.strip().split("\n")
    return lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))


async def _next(stream: AsyncIterator[str]) -> str:
    return await asyncio.wait_for(anext(stream), timeout=5)


async def test_snapshot_document_and_done(fake_redis) -> None:
    batch_id, ids = await _make_batch(fake_redis)
    stream = batch_event_stream(fake_redis, batch_id, _never)
    name, data = _parse(await _next(stream))
    assert name == "snapshot"
    assert [d["id"] for d in data["documents"]] == ids

    await repository.update_status(fake_redis, ids[0], DocumentStatus.completed, summary="sum")
    name, data = _parse(await _next(stream))
    assert (name, data["id"], data["status"], data["summary"]) == (
        "document",
        ids[0],
        "completed",
        "sum",
    )

    await repository.update_status(fake_redis, ids[1], DocumentStatus.failed, error="boom")
    name, data = _parse(await _next(stream))
    assert (name, data["error"]) == ("document", "boom")
    assert _parse(await _next(stream))[0] == "done"
    assert [f async for f in stream] == []


async def test_finished_batch_closes_after_snapshot(fake_redis) -> None:
    batch_id, ids = await _make_batch(fake_redis, 1)
    await repository.update_status(fake_redis, ids[0], DocumentStatus.completed)
    frames = [f async for f in batch_event_stream(fake_redis, batch_id, _never)]
    assert [_parse(f)[0] for f in frames] == ["snapshot", "done"]


async def test_heartbeat_and_max_duration(fake_redis) -> None:
    batch_id, _ = await _make_batch(fake_redis, 1)
    frames = [
        f
        async for f in batch_event_stream(
            fake_redis, batch_id, _never, heartbeat_seconds=0, max_duration_seconds=1.5
        )
    ]
    assert _parse(frames[0])[0] == "snapshot"
    assert ": ping\n\n" in frames[1:]
    assert all(not f.startswith("event: done") for f in frames)


async def test_disconnect_stops_stream(fake_redis) -> None:
    batch_id, _ = await _make_batch(fake_redis, 1)

    async def gone() -> bool:
        return True

    frames = [f async for f in batch_event_stream(fake_redis, batch_id, gone)]
    assert [_parse(f)[0] for f in frames] == ["snapshot"]


async def test_pubsub_closed_on_exit(fake_redis) -> None:
    batch_id, _ = await _make_batch(fake_redis, 1)
    channel = repository.events_channel(batch_id)
    stream = batch_event_stream(fake_redis, batch_id, _never)
    await _next(stream)
    assert (await fake_redis.pubsub_numsub(channel))[0][1] == 1
    await stream.aclose()
    assert (await fake_redis.pubsub_numsub(channel))[0][1] == 0


async def test_unknown_batch_404(client: AsyncClient) -> None:
    response = await client.get("/batches/nope/events")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
