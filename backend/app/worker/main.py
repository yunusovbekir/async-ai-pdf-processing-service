"""Worker entrypoint (`python -m app.worker.main`).

Connects to Redis and, in later PRs, consumes document jobs from the `docs:jobs`
stream. For now it only logs "worker started" and idles until SIGTERM/SIGINT,
then shuts down gracefully. While running it writes a readiness file used by the
compose healthcheck.
"""

import asyncio
import logging
import signal
from pathlib import Path

from app.config import get_settings
from app.logging_config import setup_logging
from app.redis_client import close_redis, get_redis

logger = logging.getLogger(__name__)

READY_FILE = Path("/tmp/worker-ready")  # probed by the compose healthcheck


async def run() -> None:
    setup_logging(get_settings().LOG_LEVEL)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    await get_redis().ping()
    await asyncio.to_thread(READY_FILE.touch)
    logger.info("worker started")
    await stop.wait()
    await asyncio.to_thread(READY_FILE.unlink, missing_ok=True)
    logger.info("worker shutting down")
    await close_redis()


if __name__ == "__main__":
    asyncio.run(run())
