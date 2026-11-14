"""Provider-agnostic entry points: global concurrency limit plus retries."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import get_settings
from app.llm.base import RetryableLLMError
from app.llm.factory import get_provider

logger = logging.getLogger(__name__)

RETRY_INITIAL_WAIT_S = 1.0
RETRY_MAX_WAIT_S = 30.0

_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Return the global semaphore limiting concurrent LLM requests."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().LLM_MAX_CONCURRENCY)
    return _semaphore


async def _run(call: Callable[[], Awaitable[str]]) -> str:
    """Run a provider call holding the semaphore per attempt, retrying transient errors."""
    retrying = AsyncRetrying(
        retry=retry_if_exception_type(RetryableLLMError),
        stop=stop_after_attempt(get_settings().LLM_MAX_RETRIES),
        wait=wait_exponential_jitter(initial=RETRY_INITIAL_WAIT_S, max=RETRY_MAX_WAIT_S),
        before_sleep=lambda state: logger.warning(
            "llm request failed, retrying attempt=%d error=%s",
            state.attempt_number,
            state.outcome.exception() if state.outcome else None,
        ),
        reraise=True,
    )
    async for attempt in retrying:
        with attempt:
            async with _get_semaphore():
                return await call()
    raise AssertionError("unreachable")


async def generate(prompt: str) -> str:
    """Generate text with the configured provider.

    Args:
        prompt: Full prompt text.

    Returns:
        The generated text (may be empty).

    Raises:
        LLMConfigError: If the provider is unknown or its API key is missing.
        RetryableLLMError: If transient failures persist after all attempts.
        Exception: Permanent provider errors propagate unchanged.
    """
    provider = get_provider()
    return await _run(lambda: provider.generate(prompt))


async def generate_from_pdf(pdf_bytes: bytes, prompt: str) -> str:
    """Generate text from a PDF with the configured provider (same limits and retries).

    Args:
        pdf_bytes: A (single-page) PDF.
        prompt: Instruction for the model.

    Returns:
        The generated text (may be empty).

    Raises:
        LLMConfigError: If the provider is unknown or its API key is missing.
        RetryableLLMError: If transient failures persist after all attempts.
    """
    provider = get_provider()
    return await _run(lambda: provider.generate_from_pdf(pdf_bytes, prompt))
