"""Shared lazily created asyncio Redis client."""

import redis.asyncio as redis

from app.config import get_settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return the shared Redis client, creating it on first use."""
    global _client
    if _client is None:
        # Must exceed the worker's XREADGROUP BLOCK (5s); redis-py 8 defaults to a 5s read timeout.
        _client = redis.from_url(
            get_settings().REDIS_URL,
            decode_responses=True,
            socket_timeout=30,
            socket_connect_timeout=5,
            health_check_interval=15,
        )
    return _client


async def close_redis() -> None:
    """Close the shared Redis client if it was created."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
