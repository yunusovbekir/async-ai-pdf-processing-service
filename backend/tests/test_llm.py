import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest
from google.genai import errors

from app import llm
from app.config import Settings, get_settings
from app.llm import client, factory
from app.llm.gemini import GeminiProvider
from app.llm.openai import OpenAIProvider


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factory, "_provider", None)
    monkeypatch.setattr(client, "_semaphore", None)
    monkeypatch.setattr(client, "RETRY_INITIAL_WAIT_S", 0.0)
    monkeypatch.setattr(client, "RETRY_MAX_WAIT_S", 0.0)


def _use(monkeypatch: pytest.MonkeyPatch, provider: object) -> None:
    monkeypatch.setattr(factory, "_provider", provider)


def _settings(**env: str) -> Settings:
    return Settings(_env_file=None, **env)


async def test_retries_transient_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = SimpleNamespace(
        generate=AsyncMock(side_effect=[llm.RetryableLLMError("429"), "done"])
    )
    _use(monkeypatch, provider)
    assert await llm.generate("hi") == "done"
    assert provider.generate.call_count == 2


async def test_permanent_error_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = SimpleNamespace(generate=AsyncMock(side_effect=ValueError("bad")))
    _use(monkeypatch, provider)
    with pytest.raises(ValueError):
        await llm.generate("hi")
    assert provider.generate.call_count == 1


async def test_retries_exhausted_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MAX_RETRIES", "3")
    get_settings.cache_clear()
    provider = SimpleNamespace(
        generate_from_pdf=AsyncMock(side_effect=llm.RetryableLLMError("503"))
    )
    _use(monkeypatch, provider)
    with pytest.raises(llm.RetryableLLMError):
        await llm.generate_from_pdf(b"%PDF", "p")
    assert provider.generate_from_pdf.call_count == 3


def test_selects_provider_from_settings() -> None:
    gemini = factory.create_provider(_settings(GEMINI_API_KEY="k"))
    assert isinstance(gemini, GeminiProvider) and gemini._model == "gemini-3.1-flash-lite"
    openai_provider = factory.create_provider(
        _settings(LLM_PROVIDER="OpenAI", OPENAI_API_KEY="k", LLM_MODEL=" gpt-x ")
    )
    assert isinstance(openai_provider, OpenAIProvider) and openai_provider._model == "gpt-x"


@pytest.mark.parametrize(
    ("provider", "message"),
    [("gemini", "GEMINI_API_KEY"), ("openai", "OPENAI_API_KEY"), ("nope", "unknown LLM_PROVIDER")],
)
def test_missing_key_or_unknown_provider(provider: str, message: str) -> None:
    with pytest.raises(llm.LLMConfigError, match=message):
        factory.create_provider(_settings(LLM_PROVIDER=provider))


def test_legacy_gemini_env_names_still_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_MAX_CONCURRENCY", "7")
    assert _settings().LLM_MAX_CONCURRENCY == 7


async def test_gemini_maps_errors_and_pdf_part() -> None:
    provider = GeminiProvider(_settings(GEMINI_API_KEY="k"), "m")
    mock = AsyncMock(
        side_effect=[
            errors.APIError(429, {"error": {"message": "q"}}),
            errors.APIError(400, {"error": {"message": "bad"}}),
            httpx.ReadTimeout("t"),
            SimpleNamespace(text="ok"),
        ]
    )
    provider._client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=mock))
    )
    with pytest.raises(llm.RetryableLLMError):
        await provider.generate("x")
    with pytest.raises(errors.APIError):
        await provider.generate("x")
    with pytest.raises(llm.RetryableLLMError):
        await provider.generate("x")
    assert await provider.generate_from_pdf(b"%PDF", "p") == "ok"
    part = mock.call_args.kwargs["contents"][0]
    assert part.inline_data.mime_type == "application/pdf"


async def test_openai_maps_errors_and_pdf_input() -> None:
    provider = OpenAIProvider(_settings(OPENAI_API_KEY="k"), "m")
    request = httpx.Request("POST", "https://x")
    rate = openai.RateLimitError("q", response=httpx.Response(429, request=request), body=None)
    bad = openai.BadRequestError("b", response=httpx.Response(400, request=request), body=None)
    mock = AsyncMock(
        side_effect=[
            rate,
            bad,
            openai.APITimeoutError(request),
            SimpleNamespace(output_text="ok"),
        ]
    )
    provider._client = SimpleNamespace(responses=SimpleNamespace(create=mock))
    with pytest.raises(llm.RetryableLLMError):
        await provider.generate("x")
    with pytest.raises(openai.BadRequestError):
        await provider.generate("x")
    with pytest.raises(llm.RetryableLLMError):
        await provider.generate("x")
    assert await provider.generate_from_pdf(b"%PDF", "p") == "ok"
    content = mock.call_args.kwargs["input"][0]["content"]
    assert (
        content[0]["file_data"]
        == "data:application/pdf;base64," + base64.b64encode(b"%PDF").decode()
    )
    assert content[1] == {"type": "input_text", "text": "p"}
