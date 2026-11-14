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
def gemini_api(monkeypatch: pytest.MonkeyPatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app import gemini_client

    mock = AsyncMock()
    fake = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=mock)))
    monkeypatch.setattr(gemini_client, "_client", fake)
    monkeypatch.setattr(gemini_client, "_semaphore", None)
    monkeypatch.setattr(gemini_client, "RETRY_INITIAL_WAIT_S", 0.0)
    monkeypatch.setattr(gemini_client, "RETRY_MAX_WAIT_S", 0.0)
    return mock


async def test_gemini_per_page_calls_keep_order(gemini_api) -> None:
    import asyncio
    from types import SimpleNamespace

    from pypdf import PdfReader

    async def fake(model, contents):
        part = contents[0]
        assert part.inline_data.mime_type == "application/pdf"
        text = PdfReader(__import__("io").BytesIO(part.inline_data.data)).pages[0].extract_text()
        # first page answers last to prove ordering is not completion order
        await asyncio.sleep(0.05 if "one" in text else 0)
        return SimpleNamespace(text=f"# {text}")

    gemini_api.side_effect = fake
    pages = await get_parser(ParserType.gemini).parse(FIXTURES / "text.pdf")
    assert gemini_api.call_count == 2
    assert [(p.page, p.content) for p in pages] == [
        (1, "# Hello page one"),
        (2, "# Second page text"),
    ]


async def test_gemini_page_failure_propagates(gemini_api) -> None:
    from types import SimpleNamespace

    from google.genai import errors

    gemini_api.side_effect = [
        SimpleNamespace(text="ok"),
        errors.APIError(503, {"error": {"message": "down"}}),
        errors.APIError(503, {"error": {"message": "down"}}),
        errors.APIError(503, {"error": {"message": "down"}}),
        errors.APIError(503, {"error": {"message": "down"}}),
        errors.APIError(503, {"error": {"message": "down"}}),
    ]
    with pytest.raises(errors.APIError):
        await get_parser(ParserType.gemini).parse(FIXTURES / "text.pdf")


async def test_gemini_missing_key_is_parser_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import gemini_client

    monkeypatch.setattr(gemini_client, "_client", None)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(ParserError, match="GEMINI_API_KEY"):
        await get_parser(ParserType.gemini).parse(FIXTURES / "text.pdf")


async def test_gemini_rejects_corrupted_pdf(gemini_api) -> None:
    with pytest.raises(ParserError):
        await get_parser(ParserType.gemini).parse(FIXTURES / "corrupted.pdf")
    gemini_api.assert_not_called()
