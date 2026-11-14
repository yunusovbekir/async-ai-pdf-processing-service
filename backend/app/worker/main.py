"""Worker entrypoint (`python -m app.worker.main`).

Consumes document jobs from the `docs:jobs` stream (consumer group `workers`),
processes them concurrently, and reclaims jobs abandoned by crashed consumers.
Writes a readiness file used by the compose healthcheck.
"""

import asyncio
import logging
import os
import signal
import socket
from pathlib import Path

import redis.asyncio as redis

from app.config import get_settings
from app.logging_config import setup_logging
from app.parsers.base import NO_TEXT_NOTE, ParserError, get_parser
from app.queue import DEAD_STREAM, GROUP, STREAM, enqueue, ensure_group
from app.redis_client import close_redis, get_redis
from app.repository import doc_key, pages_key, update_status
from app.schemas import DocumentStatus, ParserType, SummaryStatus
from app.storage import upload_path

logger = logging.getLogger(__name__)

READY_FILE = Path("/tmp/worker-ready")  # probed by the compose healthcheck
BLOCK_MS = 5000


async def summarize(client: redis.Redis, document_id: str) -> None:
    """Summary step; hook for the Gemini summarizer (skipped for now)."""
    await client.hset(doc_key(document_id), "summary_status", SummaryStatus.skipped)


async def _process(client: redis.Redis, document_id: str) -> None:
    """Parse a document, store its pages and run the summary step.

    Moves the status parsing -> summarizing -> completed. Replaces any previously stored
    pages and sets an error note when no page has text.

    Args:
        client: Redis client.
        document_id: Document to process.

    Raises:
        ParserError: Permanent parsing failure.
    """
    doc = await client.hgetall(doc_key(document_id))
    parser = get_parser(ParserType(doc["parser"]))
    await update_status(client, document_id, DocumentStatus.parsing)
    pages = await parser.parse(upload_path(document_id))

    ttl = get_settings().DATA_TTL_SECONDS
    note = "" if any(p.content for p in pages) else NO_TEXT_NOTE
    async with client.pipeline(transaction=True) as pipe:
        pipe.delete(pages_key(document_id))
        pipe.rpush(pages_key(document_id), *(p.model_dump_json() for p in pages))
        pipe.expire(pages_key(document_id), ttl)
        pipe.hset(doc_key(document_id), mapping={"page_count": len(pages), "error": note})
        await pipe.execute()

    await update_status(client, document_id, DocumentStatus.summarizing)
    await summarize(client, document_id)
    await update_status(client, document_id, DocumentStatus.completed)


async def process_message(client: redis.Redis, entry_id: str, fields: dict[str, str]) -> None:
    """Run the pipeline for one stream entry and acknowledge it.

    ParserError is permanent (document failed). Any other exception is transient:
    the job is re-enqueued with attempt+1, or dead-lettered after MAX_ATTEMPTS.

    Args:
        client: Redis client.
        entry_id: Stream entry id.
        fields: Entry fields (document_id, attempt).
    """
    document_id = fields["document_id"]
    attempt = int(fields.get("attempt", 1))
    try:
        status = await client.hget(doc_key(document_id), "status")
        if status is None:
            logger.warning("unknown document, dropping document_id=%s", document_id)
        elif status == DocumentStatus.completed:
            logger.info("already completed, skipping document_id=%s", document_id)
        else:
            await client.hset(doc_key(document_id), "attempts", attempt)
            await _process(client, document_id)
    except ParserError as exc:
        logger.warning("permanent failure document_id=%s error=%s", document_id, exc)
        await update_status(client, document_id, DocumentStatus.failed, error=str(exc))
    except Exception as exc:
        logger.exception("transient failure document_id=%s attempt=%d", document_id, attempt)
        await _handle_transient(client, document_id, attempt, exc)
    await client.xack(STREAM, GROUP, entry_id)


async def _handle_transient(
    client: redis.Redis, document_id: str, attempt: int, exc: Exception
) -> None:
    """Retry a transiently failed job, or dead-letter it once attempts are exhausted.

    Args:
        client: Redis client.
        document_id: Document that failed.
        attempt: Attempt number that just failed.
        exc: The failure cause.
    """
    if attempt < get_settings().MAX_ATTEMPTS:
        await update_status(client, document_id, DocumentStatus.queued)
        await enqueue(client, document_id, attempt + 1)
        return
    error = f"processing failed after {attempt} attempts: {exc}"
    await update_status(client, document_id, DocumentStatus.failed, error=error)
    await client.xadd(
        DEAD_STREAM, {"document_id": document_id, "attempt": attempt, "error": str(exc)}
    )
    logger.error("dead-lettered document_id=%s", document_id)


class Consumer:
    def __init__(self, client: redis.Redis, name: str, concurrency: int, claim_idle_ms: int):
        self.client = client
        self.name = name
        self.concurrency = concurrency
        self.claim_idle_ms = claim_idle_ms
        self.stop = asyncio.Event()
        self._sem = asyncio.Semaphore(concurrency)
        self._tasks: set[asyncio.Task[None]] = set()
        self._entry_ids: set[str] = set()

    def _spawn(self, entry_id: str, fields: dict[str, str]) -> None:
        """Process an entry in a background task, bounded by the semaphore.

        Entries already in flight in this consumer are ignored (e.g. re-claimed while running).

        Args:
            entry_id: Stream entry id.
            fields: Entry fields.
        """
        if entry_id in self._entry_ids:
            return
        self._entry_ids.add(entry_id)

        async def runner() -> None:
            async with self._sem:
                try:
                    await process_message(self.client, entry_id, fields)
                except Exception:
                    logger.exception("unhandled error entry_id=%s", entry_id)
                finally:
                    self._entry_ids.discard(entry_id)

        task = asyncio.create_task(runner())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def read_loop(self) -> None:
        """Read new jobs until stop is set, bounded by the concurrency limit."""
        while not self.stop.is_set():
            free = self.concurrency - len(self._tasks)
            if free <= 0:
                await asyncio.wait(self._tasks, return_when=asyncio.FIRST_COMPLETED)
                continue
            response = await self.client.xreadgroup(
                GROUP, self.name, {STREAM: ">"}, count=free, block=BLOCK_MS
            )
            if not response:
                await asyncio.sleep(0)  # fakeredis does not honor BLOCK; avoid starving the loop
            for _, entries in response or []:
                for entry_id, fields in entries:
                    self._spawn(entry_id, fields)

    async def claim_loop(self) -> None:
        """Periodically take over jobs idle longer than CLAIM_IDLE_MS."""
        interval = max(1.0, self.claim_idle_ms / 2000)
        while not self.stop.is_set():
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=interval)
                return
            except TimeoutError:
                pass
            cursor = "0-0"
            while True:
                cursor, entries, _ = await self.client.xautoclaim(
                    STREAM,
                    GROUP,
                    self.name,
                    self.claim_idle_ms,
                    start_id=cursor,
                    count=self.concurrency,
                )
                for entry_id, fields in entries:
                    logger.info("claimed entry_id=%s consumer=%s", entry_id, self.name)
                    self._spawn(entry_id, fields)
                if cursor in ("0-0", b"0-0") or not entries:
                    break

    async def run(self) -> None:
        """Run the read and claim loops until stop is set, then drain in-flight jobs."""
        claimer = asyncio.create_task(self.claim_loop())
        try:
            await self.read_loop()
        finally:
            self.stop.set()
            await claimer
            if self._tasks:
                logger.info("waiting for %d in-flight jobs", len(self._tasks))
                await asyncio.gather(*self._tasks, return_exceptions=True)


async def run() -> None:
    """Start the worker: connect, join the consumer group and consume until SIGTERM/SIGINT.

    Maintains the readiness file while running and closes Redis on exit.
    """
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    client = get_redis()
    await client.ping()
    await ensure_group(client)

    name = f"{socket.gethostname()}-{os.getpid()}"
    consumer = Consumer(client, name, settings.WORKER_CONCURRENCY, settings.CLAIM_IDLE_MS)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, consumer.stop.set)

    await asyncio.to_thread(READY_FILE.touch)
    logger.info("worker started consumer=%s", name)
    await consumer.run()
    await asyncio.to_thread(READY_FILE.unlink, missing_ok=True)
    logger.info("worker shutting down")
    await close_redis()


if __name__ == "__main__":
    asyncio.run(run())
