"""Shared async Gemini client with bounded concurrency and retries."""

import asyncio
import logging

import httpx
from google import genai
from google.genai import errors, types
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

RETRY_INITIAL_WAIT_S = 1.0
RETRY_MAX_WAIT_S = 30.0

_client: genai.Client | None = None
_semaphore: asyncio.Semaphore | None = None


class GeminiConfigError(Exception):
    """Gemini is not configured (missing API key)."""


def get_client() -> genai.Client:
    """Return the process-wide google-genai client, creating it on first use.

    Returns:
        The shared client (use `client.aio` for async calls).

    Raises:
        GeminiConfigError: If GEMINI_API_KEY is not set.
    """
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.GEMINI_API_KEY:
            raise GeminiConfigError("GEMINI_API_KEY is not set")
        _client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=settings.GEMINI_TIMEOUT_SECONDS * 1000),
        )
    return _client


def _get_semaphore() -> asyncio.Semaphore:
    """Return the global semaphore limiting concurrent Gemini requests."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().GEMINI_MAX_CONCURRENCY)
    return _semaphore


def is_retryable(exc: BaseException) -> bool:
    """Tell whether a Gemini failure is transient (429, 5xx or a timeout).

    Args:
        exc: The raised exception.

    Returns:
        True if the request should be retried.
    """
    if isinstance(exc, errors.APIError):
        return exc.code == 429 or 500 <= exc.code < 600
    return isinstance(exc, httpx.TimeoutException | TimeoutError)


async def generate(prompt: str | types.ContentListUnion) -> str:
    """Generate text with the configured model.

    Holds the global concurrency semaphore per attempt and retries transient failures
    (429, 5xx, timeouts) with exponential backoff and jitter.

    Args:
        prompt: Full prompt text, or a list of contents (e.g. text plus a PDF `Part`).

    Returns:
        The generated text (may be empty).

    Raises:
        GeminiConfigError: If GEMINI_API_KEY is not set.
        errors.APIError: On a permanent API error or once retries are exhausted.
    """
    settings = get_settings()
    client = get_client()
    retrying = AsyncRetrying(
        retry=retry_if_exception(is_retryable),
        stop=stop_after_attempt(settings.GEMINI_MAX_RETRIES),
        wait=wait_exponential_jitter(initial=RETRY_INITIAL_WAIT_S, max=RETRY_MAX_WAIT_S),
        before_sleep=lambda state: logger.warning(
            "gemini request failed, retrying attempt=%d error=%s",
            state.attempt_number,
            state.outcome.exception() if state.outcome else None,
        ),
        reraise=True,
    )
    async for attempt in retrying:
        with attempt:
            async with _get_semaphore():
                response = await client.aio.models.generate_content(
                    model=settings.GEMINI_MODEL, contents=prompt
                )
    return response.text or ""
