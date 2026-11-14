# Summarization

After parsing, the worker summarizes the whole document with Gemini (`app/summarizer.py`, `app/gemini_client.py`).

- `summarize(pages)` joins pages as `[Page N]\n<content>`, truncates to `SUMMARY_MAX_INPUT_CHARS` and asks for a concise markdown summary (short overview + key points) in the document's language. Empty text returns `""` without an API call.
- `gemini_client.generate(prompt)` uses one shared async client (`client.aio`), a global semaphore of `GEMINI_MAX_CONCURRENCY`, a request timeout (`GEMINI_TIMEOUT_SECONDS`) and tenacity retries (up to `GEMINI_MAX_RETRIES` attempts, exponential backoff + jitter) on 429, 5xx and timeouts only. A missing `GEMINI_API_KEY` raises `GeminiConfigError`.

## Outcomes

| Case | `summary_status` | Other fields |
|------|------------------|--------------|
| Summary generated | `completed` | `summary` set |
| No text in any page | `skipped` | no API call |
| Any failure (API error, retries exhausted, missing key) | `failed` | `error` = `summary failed: ...` |

A summary failure never fails the document: pages are kept and `status` is `completed`.
