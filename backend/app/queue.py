import logging

import redis.asyncio as redis
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)

STREAM = "docs:jobs"
DEAD_STREAM = "docs:jobs:dead"
GROUP = "workers"
STREAM_MAXLEN = 100_000


async def ensure_group(client: redis.Redis) -> None:
    try:
        await client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def enqueue(client: redis.Redis, document_id: str, attempt: int = 1) -> str:
    entry_id = await client.xadd(
        STREAM,
        {"document_id": document_id, "attempt": attempt},
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )
    logger.info("enqueued document_id=%s attempt=%d entry_id=%s", document_id, attempt, entry_id)
    return entry_id
