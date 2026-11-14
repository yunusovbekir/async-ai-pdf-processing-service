# Summarization

After parsing, the worker summarizes the whole document with the configured LLM provider (`app/summarizer.py`, `app/llm/`).

- `summarize(pages)` joins pages as `[Page N]\n<content>`, truncates to `SUMMARY_MAX_INPUT_CHARS` and asks for a concise markdown summary (short overview + key points) in the document's language. Empty text returns `""` without an API call.
- `llm.generate(prompt)` / `llm.generate_from_pdf(pdf_bytes, prompt)` (`app/llm/client.py`) delegate to the provider chosen by `LLM_PROVIDER` (`gemini` or `openai`, see README "Switching the LLM provider"). They hold a global semaphore of `LLM_MAX_CONCURRENCY` per attempt and use tenacity retries (up to `LLM_MAX_RETRIES` attempts, exponential backoff + jitter) on `RetryableLLMError` only: each provider maps its own 429, 5xx and timeouts to it. The request timeout is `LLM_TIMEOUT_SECONDS`. A missing API key for the selected provider (or an unknown provider) raises `LLMConfigError`.

## Outcomes

| Case | `summary_status` | Other fields |
|------|------------------|--------------|
| Summary generated | `completed` | `summary` set |
| No text in any page | `skipped` | no API call |
| Any failure (API error, retries exhausted, missing key) | `failed` | `error` = `summary failed: ...` |

A summary failure never fails the document: pages are kept and `status` is `completed`.
