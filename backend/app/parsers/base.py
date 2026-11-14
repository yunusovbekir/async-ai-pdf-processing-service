from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

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
    raise ParserError(f"parser '{parser_type}' is not supported yet")
