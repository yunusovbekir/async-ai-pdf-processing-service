"""Provider-agnostic LLM interface and shared errors."""

from typing import Protocol


class LLMConfigError(Exception):
    """The selected LLM provider is unknown or not configured (e.g. missing API key)."""


class RetryableLLMError(Exception):
    """A transient provider failure (429, 5xx, timeout) that is safe to retry."""


class LLMProvider(Protocol):
    """Minimal contract every LLM provider implements.

    Implementations must raise `RetryableLLMError` (chained from the SDK error) for
    transient failures and let permanent errors propagate unchanged.
    """

    async def generate(self, prompt: str) -> str:
        """Generate text from a text prompt (may return an empty string)."""
        ...

    async def generate_from_pdf(self, pdf_bytes: bytes, prompt: str) -> str:
        """Generate text from a (single-page) PDF plus an instruction prompt."""
        ...
