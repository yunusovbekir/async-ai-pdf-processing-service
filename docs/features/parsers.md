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

The `gemini` parser is accepted at upload but not implemented yet: `get_parser` raises `ParserError`, so such documents end as `failed` ("parser 'gemini' is not supported yet").
