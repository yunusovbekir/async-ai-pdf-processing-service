"""Gemini provider (google-genai SDK)."""

import httpx
from google import genai
from google.genai import errors, types

from app.config import Settings
from app.llm.base import LLMConfigError, RetryableLLMError


class GeminiProvider:
    """LLM provider backed by Google Gemini."""

    name = "gemini"
    default_model = "gemini-3.1-flash-lite"

    def __init__(self, settings: Settings, model: str) -> None:
        """Create the client.

        Raises:
            LLMConfigError: If GEMINI_API_KEY is not set.
        """
        if not settings.GEMINI_API_KEY:
            raise LLMConfigError("GEMINI_API_KEY is not set")
        self._model = model
        self._client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=settings.LLM_TIMEOUT_SECONDS * 1000),
        )

    async def generate(self, prompt: str) -> str:
        """Generate text from a prompt."""
        return await self._call(prompt)

    async def generate_from_pdf(self, pdf_bytes: bytes, prompt: str) -> str:
        """Generate text from a PDF sent inline together with the prompt."""
        part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        return await self._call([part, prompt])

    async def _call(self, contents: types.ContentListUnion) -> str:
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model, contents=contents
            )
        except errors.APIError as exc:
            if exc.code == 429 or 500 <= exc.code < 600:
                raise RetryableLLMError(str(exc)) from exc
            raise
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise RetryableLLMError(f"timeout: {exc}") from exc
        return response.text or ""
