"""Document summarization with the configured LLM provider."""

import logging

from app import llm
from app.config import get_settings
from app.parsers.base import PageContent

logger = logging.getLogger(__name__)

PROMPT = """Summarize the following document in the same language as the document.
Reply in concise markdown: a short overview paragraph, then a "Key points" bullet list.
Do not add information that is not in the document.

Document:
{text}"""


def build_text(pages: list[PageContent], max_chars: int) -> str:
    """Join page contents with page markers and truncate to a character budget.

    Args:
        pages: Parsed pages.
        max_chars: Maximum length of the returned text.

    Returns:
        The joined text, or "" if no page has content.
    """
    if not any(p.content.strip() for p in pages):
        return ""
    text = "\n\n".join(f"[Page {p.page}]\n{p.content}" for p in pages)
    return text[:max_chars]


async def summarize(pages: list[PageContent]) -> str:
    """Summarize a document's pages.

    Args:
        pages: Parsed pages.

    Returns:
        A markdown summary, or "" (without calling the API) if the document has no text.

    Raises:
        LLMConfigError: If the configured provider is unknown or its API key is missing.
        Exception: If the provider call fails after retries.
    """
    text = build_text(pages, get_settings().SUMMARY_MAX_INPUT_CHARS)
    if not text:
        return ""
    return (await llm.generate(PROMPT.format(text=text))).strip()
