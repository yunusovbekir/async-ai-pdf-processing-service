# Parsers (`backend/app/parsers/`)

- `base.py`: `Parser` protocol (`async parse(path) -> list[PageContent]`), `PageContent {page (1-based), content}`, `ParserError` (permanent, user-facing failure) and `get_parser(ParserType)`.
- `pypdf_parser.py`: extracts text per page with pypdf inside `asyncio.to_thread`.

pypdf behavior

| Input                                   | Result                                                        |
|-----------------------------------------|---------------------------------------------------------------|
| Text PDF                                | One `PageContent` per page, text stripped                     |
| Encrypted PDF                           | Tries the empty password; otherwise `ParserError("encrypted PDF not supported")` |
| Corrupted/unreadable PDF                | `ParserError("could not read PDF: ...")`                      |
| Zero pages                              | `ParserError("PDF has no pages")`                             |
| No text on any page (scanned/blank)     | Pages kept with empty content; the worker completes the document with `error` = "no text layer found; try the gemini parser" |

## gemini parser

`gemini_parser.py`: validates the PDF via the shared `open_pdf` helper (in `base.py`, also used by pypdf), splits it into single-page PDFs with pypdf in a thread, and sends each page as `Part.from_bytes(mime_type="application/pdf")` plus a prompt asking for GitHub-flavored markdown (headings/lists/tables kept, images and charts described briefly in italics, markdown only). Pages run concurrently via `gemini_client.generate` (shared semaphore and retries); results keep page order.

| Situation                     | Result                                                                    |
|-------------------------------|---------------------------------------------------------------------------|
| `GEMINI_API_KEY` missing      | `ParserError("gemini parser unavailable: GEMINI_API_KEY is not set")`     |
| Encrypted/corrupted/empty PDF | Same `ParserError`s as pypdf, no API calls                                |
| A page fails after retries    | Exception propagates: transient failure of the whole document (worker retries, then dead-letters) |
