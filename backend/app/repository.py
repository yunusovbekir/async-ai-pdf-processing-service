import json
import logging
from datetime import UTC, datetime

import redis.asyncio as redis

from app.config import get_settings
from app.schemas import DocumentStatus, ParserType, SummaryStatus

logger = logging.getLogger(__name__)


def doc_key(document_id: str) -> str:
    """Redis key of the document hash."""
    return f"doc:{document_id}"


def pages_key(document_id: str) -> str:
    """Redis key of the document pages list."""
    return f"doc:{document_id}:pages"


def batch_key(batch_id: str) -> str:
    """Redis key of the batch hash."""
    return f"batch:{batch_id}"


def batch_docs_key(batch_id: str) -> str:
    """Redis key of the batch document id list."""
    return f"batch:{batch_id}:docs"


def events_channel(batch_id: str) -> str:
    """Pub/Sub channel for batch status events."""
    return f"batch:{batch_id}:events"


def _now() -> str:
    """Current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


async def create_batch(
    client: redis.Redis, batch_id: str, parser: ParserType, documents: list[tuple[str, str]]
) -> None:
    """Atomically store a batch and its documents (id, filename) as queued."""
    ttl = get_settings().DATA_TTL_SECONDS
    now = _now()
    async with client.pipeline(transaction=True) as pipe:
        pipe.hset(
            batch_key(batch_id), mapping={"id": batch_id, "parser": parser, "created_at": now}
        )
        pipe.expire(batch_key(batch_id), ttl)
        for document_id, filename in documents:
            pipe.hset(
                doc_key(document_id),
                mapping={
                    "id": document_id,
                    "batch_id": batch_id,
                    "filename": filename,
                    "parser": parser,
                    "status": DocumentStatus.queued,
                    "summary_status": SummaryStatus.pending,
                    "summary": "",
                    "error": "",
                    "page_count": "",
                    "attempts": 0,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            pipe.expire(doc_key(document_id), ttl)
            pipe.rpush(batch_docs_key(batch_id), document_id)
        pipe.expire(batch_docs_key(batch_id), ttl)
        await pipe.execute()
    logger.info("batch created batch_id=%s documents=%d", batch_id, len(documents))


def _clean(raw: dict[str, str]) -> dict[str, object]:
    """Convert a raw hash into typed values, mapping empty strings to None."""
    data: dict[str, object] = {k: (v if v != "" else None) for k, v in raw.items()}
    data["attempts"] = int(raw.get("attempts") or 0)
    if data.get("page_count") is not None:
        data["page_count"] = int(str(data["page_count"]))
    return data


async def get_document(
    client: redis.Redis, document_id: str, with_pages: bool = True
) -> dict[str, object] | None:
    """Fetch a document (optionally with pages), or None if unknown."""
    raw = await client.hgetall(doc_key(document_id))
    if not raw:
        return None
    data = _clean(raw)
    if with_pages:
        items = await client.lrange(pages_key(document_id), 0, -1)
        data["pages"] = [json.loads(item) for item in items]
    return data


async def get_batch(client: redis.Redis, batch_id: str) -> dict[str, object] | None:
    """Fetch a batch with its documents (no pages), or None if unknown."""
    raw = await client.hgetall(batch_key(batch_id))
    if not raw:
        return None
    ids = await client.lrange(batch_docs_key(batch_id), 0, -1)
    documents = [d for d in [await get_document(client, i, with_pages=False) for i in ids] if d]
    return {**raw, "documents": documents}


async def update_status(
    client: redis.Redis,
    document_id: str,
    status: DocumentStatus,
    **fields: str | int,
) -> None:
    """Set status (plus optional extra hash fields) and publish the change event."""
    batch_id = await client.hget(doc_key(document_id), "batch_id")
    if batch_id is None:
        logger.warning("status update for unknown document_id=%s", document_id)
        return
    ttl = get_settings().DATA_TTL_SECONDS
    mapping = {**fields, "status": status, "updated_at": _now()}
    async with client.pipeline(transaction=True) as pipe:
        pipe.hset(doc_key(document_id), mapping=mapping)
        pipe.expire(doc_key(document_id), ttl)
        pipe.publish(
            events_channel(batch_id), json.dumps({"document_id": document_id, "status": status})
        )
        await pipe.execute()
    logger.info(
        "status updated document_id=%s batch_id=%s status=%s", document_id, batch_id, status
    )
