import asyncio
import logging
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.parsers.base import PageContent, ParserError

logger = logging.getLogger(__name__)


def _extract(path: Path) -> list[PageContent]:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ParserError("encrypted PDF not supported")
        pages = [
            PageContent(page=i, content=(page.extract_text() or "").strip())
            for i, page in enumerate(reader.pages, start=1)
        ]
    except ParserError:
        raise
    except (PyPdfError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ParserError(f"could not read PDF: {exc}") from exc
    if not pages:
        raise ParserError("PDF has no pages")
    return pages


class PyPdfParser:
    async def parse(self, path: Path) -> list[PageContent]:
        """Extract text per page with pypdf (off the event loop).

        Raises:
            ParserError: If the PDF is encrypted, unreadable or has no pages.
        """
        return await asyncio.to_thread(_extract, path)
