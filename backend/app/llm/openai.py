"""OpenAI provider (openai SDK, Responses API)."""

import base64

import openai

from app.config import Settings
from app.llm.base import LLMConfigError, RetryableLLMError


class OpenAIProvider:
    """LLM provider backed by OpenAI."""

    name = "openai"
    default_model = "gpt-5-mini"

    def __init__(self, settings: Settings, model: str) -> None:
        """Create the client (SDK-level retries are disabled; the shared retry handles them).

        Raises:
            LLMConfigError: If OPENAI_API_KEY is not set.
        """
        if not settings.OPENAI_API_KEY:
            raise LLMConfigError("OPENAI_API_KEY is not set")
        self._model = model
        self._client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=0,
        )

    async def generate(self, prompt: str) -> str:
        """Generate text from a prompt."""
        return await self._call([{"type": "input_text", "text": prompt}])

    async def generate_from_pdf(self, pdf_bytes: bytes, prompt: str) -> str:
        """Generate text from a PDF sent as a base64 `input_file` together with the prompt."""
        data = base64.b64encode(pdf_bytes).decode()
        return await self._call(
            [
                {
                    "type": "input_file",
                    "filename": "page.pdf",
                    "file_data": f"data:application/pdf;base64,{data}",
                },
                {"type": "input_text", "text": prompt},
            ]
        )

    async def _call(self, content: list[dict[str, str]]) -> str:
        try:
            response = await self._client.responses.create(
                model=self._model, input=[{"role": "user", "content": content}]
            )
        except openai.APIStatusError as exc:
            if exc.status_code == 429 or 500 <= exc.status_code < 600:
                raise RetryableLLMError(str(exc)) from exc
            raise
        except openai.APIConnectionError as exc:  # includes APITimeoutError
            raise RetryableLLMError(f"connection error: {exc}") from exc
        return response.output_text or ""
