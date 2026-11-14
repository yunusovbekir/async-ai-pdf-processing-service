import asyncio
import shutil
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app import llm, queue, repository
from app.parsers.base import NO_TEXT_NOTE
from app.schemas import ParserType
from app.storage import upload_path
from app.worker.main import Consumer, process_message

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(return_value="## Summary\n- point")
    monkeypatch.setattr(llm, "generate", mock)
    return mock


async def _submit(fake_redis, fixture: str) -> str:
    document_id = "doc1"
    path = upload_path(document_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / fixture, path)
    await repository.create_batch(fake_redis, "b1", ParserType.pypdf, [(document_id, fixture)])
    await queue.enqueue(fake_redis, document_id)
    return document_id


async def _read(fake_redis) -> list[tuple[str, dict[str, str]]]:
    response = await fake_redis.xreadgroup(queue.GROUP, "c1", {queue.STREAM: ">"}, count=10)
    return response[0][1] if response else []


async def _run_once(fake_redis) -> None:
    for entry_id, fields in await _read(fake_redis):
        await process_message(fake_redis, entry_id, fields)


async def test_end_to_end(fake_redis, fake_llm) -> None:
    document_id = await _submit(fake_redis, "text.pdf")
    pubsub = fake_redis.pubsub()
    await pubsub.subscribe(repository.events_channel("b1"))
    await _run_once(fake_redis)

    doc = await repository.get_document(fake_redis, document_id)
    assert doc["status"] == "completed"
    assert doc["summary_status"] == "completed"
    assert doc["summary"] == "## Summary\n- point"
    assert doc["page_count"] == 2
    assert doc["error"] is None
    assert [p["content"] for p in doc["pages"]] == ["Hello page one", "Second page text"]
    assert (await fake_redis.xpending(queue.STREAM, queue.GROUP))["pending"] == 0

    statuses = []
    while message := await pubsub.get_message(timeout=0.1):
        if message["type"] == "message":
            statuses.append(message["data"])
    assert [s.split('"')[-2] for s in statuses] == ["parsing", "summarizing", "completed"]


async def test_completed_document_is_skipped(fake_redis) -> None:
    document_id = await _submit(fake_redis, "text.pdf")
    await _run_once(fake_redis)
    await queue.enqueue(fake_redis, document_id)
    upload_path(document_id).unlink()
    await _run_once(fake_redis)
    assert (await repository.get_document(fake_redis, document_id))["status"] == "completed"
    assert (await fake_redis.xpending(queue.STREAM, queue.GROUP))["pending"] == 0


async def test_blank_pdf_completes_with_note(fake_redis) -> None:
    document_id = await _submit(fake_redis, "blank.pdf")
    await _run_once(fake_redis)
    doc = await repository.get_document(fake_redis, document_id)
    assert doc["status"] == "completed"
    assert doc["page_count"] == 2
    assert doc["error"] == NO_TEXT_NOTE


async def test_permanent_failure(fake_redis) -> None:
    document_id = await _submit(fake_redis, "corrupted.pdf")
    await _run_once(fake_redis)
    doc = await repository.get_document(fake_redis, document_id)
    assert doc["status"] == "failed"
    assert "could not read PDF" in doc["error"]
    assert await fake_redis.xlen(queue.DEAD_STREAM) == 0
    assert (await fake_redis.xpending(queue.STREAM, queue.GROUP))["pending"] == 0


async def test_transient_retry_then_dead_letter(
    fake_redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    document_id = await _submit(fake_redis, "text.pdf")
    upload_path(document_id).unlink()  # FileNotFoundError is not a ParserError

    await _run_once(fake_redis)
    doc = await repository.get_document(fake_redis, document_id)
    assert doc["status"] == "queued"
    assert doc["attempts"] == 1
    assert await fake_redis.xlen(queue.DEAD_STREAM) == 0

    await _run_once(fake_redis)
    await _run_once(fake_redis)
    doc = await repository.get_document(fake_redis, document_id)
    assert doc["status"] == "failed"
    assert doc["attempts"] == 3
    dead = await fake_redis.xrange(queue.DEAD_STREAM)
    assert len(dead) == 1
    assert dead[0][1]["document_id"] == document_id
    assert (await fake_redis.xpending(queue.STREAM, queue.GROUP))["pending"] == 0


async def test_consumer_loop_processes_and_stops(fake_redis) -> None:
    document_id = await _submit(fake_redis, "text.pdf")
    consumer = Consumer(fake_redis, "test-consumer", concurrency=2, claim_idle_ms=60_000)
    task = asyncio.create_task(consumer.run())
    for _ in range(100):
        doc = await repository.get_document(fake_redis, document_id, with_pages=False)
        if doc["status"] == "completed":
            break
        await asyncio.sleep(0.05)
    consumer.stop.set()
    await asyncio.wait_for(task, timeout=10)
    assert doc["status"] == "completed"


async def test_summary_failure_keeps_document_completed(fake_redis, fake_llm) -> None:
    fake_llm.side_effect = RuntimeError("boom")
    document_id = await _submit(fake_redis, "text.pdf")
    await _run_once(fake_redis)

    doc = await repository.get_document(fake_redis, document_id)
    assert doc["status"] == "completed"
    assert doc["summary_status"] == "failed"
    assert "boom" in doc["error"]
    assert doc["summary"] is None
    assert len(doc["pages"]) == 2


async def test_empty_text_skips_summary(fake_redis, fake_llm) -> None:
    document_id = await _submit(fake_redis, "blank.pdf")
    await _run_once(fake_redis)

    doc = await repository.get_document(fake_redis, document_id)
    assert doc["status"] == "completed"
    assert doc["summary_status"] == "skipped"
    fake_llm.assert_not_called()
