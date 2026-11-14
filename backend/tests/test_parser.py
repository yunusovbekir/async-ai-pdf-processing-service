from pathlib import Path

import pytest

from app.parsers.base import ParserError, get_parser
from app.schemas import ParserType

FIXTURES = Path(__file__).parent / "fixtures"


async def test_text_pdf_per_page() -> None:
    pages = await get_parser(ParserType.pypdf).parse(FIXTURES / "text.pdf")
    assert [(p.page, p.content) for p in pages] == [
        (1, "Hello page one"),
        (2, "Second page text"),
    ]


async def test_blank_pdf_keeps_pages() -> None:
    pages = await get_parser(ParserType.pypdf).parse(FIXTURES / "blank.pdf")
    assert [p.content for p in pages] == ["", ""]


async def test_corrupted_pdf_raises() -> None:
    with pytest.raises(ParserError):
        await get_parser(ParserType.pypdf).parse(FIXTURES / "corrupted.pdf")


async def test_encrypted_pdf_raises(tmp_path: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(FIXTURES / "text.pdf"))
    writer.encrypt("secret")
    path = tmp_path / "enc.pdf"
    with path.open("wb") as handle:
        writer.write(handle)
    with pytest.raises(ParserError, match="encrypted PDF not supported"):
        await get_parser(ParserType.pypdf).parse(path)


@pytest.fixture
def llm_pdf(monkeypatch: pytest.MonkeyPatch):
    from unittest.mock import AsyncMock

    from app import llm

    mock = AsyncMock()
    monkeypatch.setattr(llm, "get_provider", lambda: object())
    monkeypatch.setattr(llm, "generate_from_pdf", mock)
    return mock


async def test_llm_per_page_calls_keep_order(llm_pdf) -> None:
    import asyncio
    import io

    from pypdf import PdfReader

    async def fake(pdf_bytes, prompt):
        text = PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text()
        # first page answers last to prove ordering is not completion order
        await asyncio.sleep(0.05 if "one" in text else 0)
        return f"# {text}"

    llm_pdf.side_effect = fake
    pages = await get_parser(ParserType.gemini).parse(FIXTURES / "text.pdf")
    assert llm_pdf.call_count == 2
    assert [(p.page, p.content) for p in pages] == [
        (1, "# Hello page one"),
        (2, "# Second page text"),
    ]


async def test_llm_page_failure_propagates(llm_pdf) -> None:
    from app import llm

    llm_pdf.side_effect = [llm.RetryableLLMError("down"), "ok"]
    with pytest.raises(llm.RetryableLLMError):
        await get_parser(ParserType.gemini).parse(FIXTURES / "text.pdf")


@pytest.mark.parametrize(
    ("provider", "key"), [("gemini", "GEMINI_API_KEY"), ("openai", "OPENAI_API_KEY")]
)
async def test_missing_key_is_parser_error(
    monkeypatch: pytest.MonkeyPatch, provider: str, key: str
) -> None:
    from app.config import get_settings
    from app.llm import factory

    monkeypatch.setattr(factory, "_provider", None)
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ParserError, match=key):
        await get_parser(ParserType.gemini).parse(FIXTURES / "text.pdf")


async def test_llm_rejects_corrupted_pdf(llm_pdf) -> None:
    with pytest.raises(ParserError):
        await get_parser(ParserType.gemini).parse(FIXTURES / "corrupted.pdf")
    llm_pdf.assert_not_called()


@pytest.mark.parametrize("parser", [ParserType.llm, ParserType.gemini])
async def test_llm_and_legacy_gemini_values_use_llm_parser(llm_pdf, parser) -> None:
    llm_pdf.return_value = "x"
    pages = await get_parser(parser).parse(FIXTURES / "text.pdf")
    assert [p.content for p in pages] == ["x", "x"]
