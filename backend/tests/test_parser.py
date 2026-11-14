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
