from pathlib import Path
from typing import Protocol

from pydantic import BaseModel
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.schemas import ParserType

NO_TEXT_NOTE = "no text layer found; try the gemini parser"


class PageContent(BaseModel):
    page: int
    content: str


class ParserError(Exception):
    """A permanent, user-facing parsing failure (never retried)."""


class Parser(Protocol):
    async def parse(self, path: Path) -> list[PageContent]:
        """Extract the content of every page, in order (1-based page numbers)."""
        ...


def open_pdf(path: Path) -> PdfReader:
    """Open a PDF and validate it (shared by all parsers).

    Args:
        path: PDF file path.

    Returns:
        A decrypted reader with at least one page.

    Raises:
        ParserError: If the PDF is encrypted, unreadable or has no pages.
    """
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ParserError("encrypted PDF not supported")
        page_count = len(reader.pages)
    except ParserError:
        raise
    except (PyPdfError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ParserError(f"could not read PDF: {exc}") from exc
    if page_count == 0:
        raise ParserError("PDF has no pages")
    return reader


def get_parser(parser_type: ParserType) -> Parser:
    """Return the parser implementation for a parser type.

    Args:
        parser_type: Parser chosen at upload time.

    Returns:
        A parser instance.

    Raises:
        ParserError: If the parser is not available.
    """
    if parser_type == ParserType.pypdf:
        from app.parsers.pypdf_parser import PyPdfParser

        return PyPdfParser()
    if parser_type == ParserType.gemini:
        from app.parsers.gemini_parser import GeminiParser

        return GeminiParser()
    raise ParserError(f"parser '{parser_type}' is not supported yet")
