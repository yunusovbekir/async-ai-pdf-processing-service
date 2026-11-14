"""Redis Streams job queue."""

import logging

import redis.asyncio as redis
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)

STREAM = "docs:jobs"
DEAD_STREAM = "docs:jobs:dead"
GROUP = "workers"
STREAM_MAXLEN = 100_000


async def ensure_group(client: redis.Redis) -> None:
    """Create the stream and consumer group if missing (idempotent).

    Args:
        client: Redis client.
    """
    try:
        await client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def enqueue(client: redis.Redis, document_id: str, attempt: int = 1) -> str:
    """Add a processing job to the stream.

    Args:
        client: Redis client.
        document_id: Document to process.
        attempt: Attempt number for this job.

    Returns:
        The stream entry id.
    """
    entry_id = await client.xadd(
        STREAM,
        {"document_id": document_id, "attempt": attempt},
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )
    logger.info("enqueued document_id=%s attempt=%d entry_id=%s", document_id, attempt, entry_id)
    return entry_id
