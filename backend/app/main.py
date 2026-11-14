"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import queue
from app.api.documents import router as documents_router
from app.api.events import router as events_router
from app.config import get_settings
from app.logging_config import setup_logging
from app.redis_client import close_redis, get_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Set up logging and the job stream on startup; close Redis on shutdown."""
    setup_logging(get_settings().LOG_LEVEL)
    await queue.ensure_group(get_redis())
    logger.info("api started")
    yield
    await close_redis()
    logger.info("api stopped")


app = FastAPI(title="PDF processing service", lifespan=lifespan)
app.include_router(documents_router)
app.include_router(events_router)


@app.get("/health")
async def health() -> JSONResponse:
    """Report API and Redis health."""
    try:
        await get_redis().ping()
    except Exception:
        logger.exception("redis health check failed")
        return JSONResponse({"status": "degraded", "redis": "down"}, status_code=503)
    return JSONResponse({"status": "ok", "redis": "up"})
