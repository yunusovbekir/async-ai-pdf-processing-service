"""Shared lazily created asyncio Redis client."""

import redis.asyncio as redis

from app.config import get_settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return the shared Redis client, creating it on first use."""
    global _client
    if _client is None:
        _client = redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    return _client


async def close_redis() -> None:
    """Close the shared Redis client if it was created."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
