from unittest.mock import AsyncMock

import pytest

from app import llm, summarizer
from app.config import get_settings
from app.parsers.base import PageContent


@pytest.fixture
def mock_llm(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Replace the LLM entry point used by the summarizer."""
    mock = AsyncMock()
    monkeypatch.setattr(llm, "generate", mock)
    return mock


async def test_summarize_returns_text(mock_llm: AsyncMock) -> None:
    mock_llm.return_value = " Overview\n- a "
    pages = [PageContent(page=1, content="one"), PageContent(page=2, content="two")]

    assert await summarizer.summarize(pages) == "Overview\n- a"
    prompt = mock_llm.call_args.args[0]
    assert "[Page 1]\none" in prompt and "[Page 2]\ntwo" in prompt


async def test_input_is_truncated(mock_llm: AsyncMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUMMARY_MAX_INPUT_CHARS", "20")
    get_settings.cache_clear()
    mock_llm.return_value = "ok"

    await summarizer.summarize([PageContent(page=1, content="x" * 500)])
    assert "x" * 20 not in mock_llm.call_args.args[0].split("Document:\n")[1]


async def test_empty_text_skips_api(mock_llm: AsyncMock) -> None:
    assert await summarizer.summarize([PageContent(page=1, content="  ")]) == ""
    mock_llm.assert_not_called()
