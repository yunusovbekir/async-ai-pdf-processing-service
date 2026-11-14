from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import errors

from app import gemini_client, summarizer
from app.config import get_settings
from app.parsers.base import PageContent


@pytest.fixture
def mock_api(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Patch the google-genai client and make retries instant."""
    generate_content = AsyncMock()
    fake = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    monkeypatch.setattr(gemini_client, "_client", fake)
    monkeypatch.setattr(gemini_client, "_semaphore", None)
    monkeypatch.setattr(gemini_client, "RETRY_INITIAL_WAIT_S", 0.0)
    monkeypatch.setattr(gemini_client, "RETRY_MAX_WAIT_S", 0.0)
    return generate_content


async def test_summarize_returns_text(mock_api: AsyncMock) -> None:
    mock_api.return_value = SimpleNamespace(text=" Overview\n- a ")
    pages = [PageContent(page=1, content="one"), PageContent(page=2, content="two")]

    assert await summarizer.summarize(pages) == "Overview\n- a"
    prompt = mock_api.call_args.kwargs["contents"]
    assert "[Page 1]\none" in prompt and "[Page 2]\ntwo" in prompt


async def test_input_is_truncated(mock_api: AsyncMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUMMARY_MAX_INPUT_CHARS", "20")
    get_settings.cache_clear()
    mock_api.return_value = SimpleNamespace(text="ok")

    await summarizer.summarize([PageContent(page=1, content="x" * 500)])
    assert "x" * 20 not in mock_api.call_args.kwargs["contents"].split("Document:\n")[1]


async def test_retries_on_429_then_succeeds(mock_api: AsyncMock) -> None:
    mock_api.side_effect = [
        errors.APIError(429, {"error": {"message": "quota"}}),
        SimpleNamespace(text="done"),
    ]
    assert await gemini_client.generate("hi") == "done"
    assert mock_api.call_count == 2


async def test_permanent_error_is_not_retried(mock_api: AsyncMock) -> None:
    mock_api.side_effect = errors.APIError(400, {"error": {"message": "bad"}})
    with pytest.raises(errors.APIError):
        await gemini_client.generate("hi")
    assert mock_api.call_count == 1


async def test_empty_text_skips_api(mock_api: AsyncMock) -> None:
    assert await summarizer.summarize([PageContent(page=1, content="  ")]) == ""
    mock_api.assert_not_called()


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini_client, "_client", None)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(gemini_client.GeminiConfigError):
        gemini_client.get_client()
