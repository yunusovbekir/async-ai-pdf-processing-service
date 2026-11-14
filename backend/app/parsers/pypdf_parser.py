"""pypdf parser: local text-layer extraction."""

import asyncio
import logging
from pathlib import Path

from pypdf.errors import PyPdfError

from app.parsers.base import PageContent, ParserError, open_pdf

logger = logging.getLogger(__name__)


def _extract(path: Path) -> list[PageContent]:
    reader = open_pdf(path)
    try:
        return [
            PageContent(page=i, content=(page.extract_text() or "").strip())
            for i, page in enumerate(reader.pages, start=1)
        ]
    except (PyPdfError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ParserError(f"could not read PDF: {exc}") from exc


class PyPdfParser:
    """Parser that extracts the text layer of each page with pypdf."""

    async def parse(self, path: Path) -> list[PageContent]:
        """Extract text per page with pypdf (off the event loop).

        Raises:
            ParserError: If the PDF is encrypted, unreadable or has no pages.
        """
        return await asyncio.to_thread(_extract, path)
