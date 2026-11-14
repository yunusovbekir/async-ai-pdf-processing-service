"""LLM parser (API value `gemini`): converts each PDF page to markdown."""

import asyncio
import io
import logging
from pathlib import Path

from pypdf import PdfWriter
from pypdf.errors import PyPdfError

from app import llm
from app.parsers.base import PageContent, ParserError, open_pdf

logger = logging.getLogger(__name__)

PROMPT = (
    "Convert this page to clean GitHub-flavored markdown. Preserve headings, lists and "
    "tables. Describe images and charts briefly in italics. Output only markdown."
)


def _split(path: Path) -> list[bytes]:
    """Split a PDF into single-page PDFs (blocking; run in a thread)."""
    reader = open_pdf(path)
    chunks: list[bytes] = []
    try:
        for page in reader.pages:
            writer = PdfWriter()
            writer.add_page(page)
            buffer = io.BytesIO()
            writer.write(buffer)
            chunks.append(buffer.getvalue())
    except (PyPdfError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ParserError(f"could not read PDF: {exc}") from exc
    return chunks


class GeminiParser:
    """Parser that asks the configured LLM to convert every page to markdown."""

    async def parse(self, path: Path) -> list[PageContent]:
        """Convert each page to markdown with the configured LLM, preserving page order.

        Pages are sent concurrently through the shared LLM semaphore/retry helper.
        A page that still fails after retries raises its exception, which the worker
        treats as a transient failure of the whole document.

        Raises:
            ParserError: If the PDF is invalid or the provider's API key is not set.
        """
        try:
            llm.get_provider()
        except llm.LLMConfigError as exc:
            raise ParserError(f"gemini parser unavailable: {exc}") from exc
        chunks = await asyncio.to_thread(_split, path)
        results = await asyncio.gather(*(self._convert(chunk) for chunk in chunks))
        return [PageContent(page=i, content=text) for i, text in enumerate(results, start=1)]

    @staticmethod
    async def _convert(chunk: bytes) -> str:
        """Convert one single-page PDF to markdown."""
        return (await llm.generate_from_pdf(chunk, PROMPT)).strip()
