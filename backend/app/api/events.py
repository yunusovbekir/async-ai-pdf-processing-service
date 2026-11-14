"""Server-Sent Events endpoint streaming document status changes of a batch."""

import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app import repository
from app.config import get_settings
from app.redis_client import get_redis
from app.schemas import BatchResponse, DocumentStatus, DocumentSummaryView

logger = logging.getLogger(__name__)

router = APIRouter()

RedisDep = Annotated[redis.Redis, Depends(get_redis)]

TERMINAL = {DocumentStatus.completed.value, DocumentStatus.failed.value}
POLL_SECONDS = 1.0


def _event(name: str, data: str) -> str:
    return f"event: {name}\ndata: {data}\n\n"


def _all_terminal(statuses: dict[str, str]) -> bool:
    return all(status in TERMINAL for status in statuses.values())


async def batch_event_stream(
    client: redis.Redis,
    batch_id: str,
    is_disconnected: Callable[[], Awaitable[bool]],
    heartbeat_seconds: float | None = None,
    max_duration_seconds: float | None = None,
) -> AsyncIterator[str]:
    """Yield SSE frames for a batch: snapshot, document updates, heartbeats and done.

    Subscribes before reading the snapshot so no status change is missed. Uses a
    dedicated Pub/Sub connection that is always released on exit. Ends after `done`,
    on client disconnect, or after the maximum duration (the client may reconnect).

    Args:
        client: Redis client.
        batch_id: Batch identifier.
        is_disconnected: Async callable returning True once the client went away.
        heartbeat_seconds: Interval of `: ping` comments (default SSE_HEARTBEAT_SECONDS).
        max_duration_seconds: Maximum stream lifetime (default SSE_MAX_DURATION_SECONDS).

    Yields:
        Encoded SSE frames.
    """
    settings = get_settings()
    heartbeat = (
        heartbeat_seconds if heartbeat_seconds is not None else settings.SSE_HEARTBEAT_SECONDS
    )
    max_duration = (
        max_duration_seconds
        if max_duration_seconds is not None
        else settings.SSE_MAX_DURATION_SECONDS
    )
    channel = repository.events_channel(batch_id)
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(channel)
        batch = await repository.get_batch(client, batch_id)
        if batch is None:
            return
        snapshot = BatchResponse.model_validate(batch)
        yield _event("snapshot", snapshot.model_dump_json())
        statuses = {d.id: d.status.value for d in snapshot.documents}
        if _all_terminal(statuses):
            yield _event("done", "{}")
            return

        started = last_sent = time.monotonic()
        while time.monotonic() - started < max_duration:
            if await is_disconnected():
                logger.info("sse client disconnected batch_id=%s", batch_id)
                return
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=POLL_SECONDS)
            if message is not None:
                document_id = json.loads(message["data"])["document_id"]
                raw = await repository.get_document(client, document_id, with_pages=False)
                if raw is not None:
                    view = DocumentSummaryView.model_validate(raw)
                    statuses[view.id] = view.status.value
                    yield _event("document", view.model_dump_json())
                    last_sent = time.monotonic()
                    if _all_terminal(statuses):
                        yield _event("done", "{}")
                        return
            elif time.monotonic() - last_sent >= heartbeat:
                yield ": ping\n\n"
                last_sent = time.monotonic()
        logger.info("sse max duration reached batch_id=%s", batch_id)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


@router.get("/batches/{batch_id}/events")
async def batch_events(batch_id: str, request: Request, client: RedisDep) -> StreamingResponse:
    """Stream document status changes of a batch as Server-Sent Events.

    Args:
        batch_id: Batch identifier.
        request: Incoming request, used to detect client disconnects.
        client: Redis client.

    Raises:
        HTTPException: 404 if the batch is unknown.
    """
    if await repository.get_batch(client, batch_id) is None:
        raise HTTPException(404, "batch not found")
    return StreamingResponse(
        batch_event_stream(client, batch_id, request.is_disconnected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
