# Async PDF processing service

Upload PDFs, parse them per page (pypdf or Gemini) and summarize with Gemini. FastAPI + Redis Streams worker.

## Run

```bash
cp .env.example .env   # set GEMINI_API_KEY when needed
docker compose up --build
curl localhost:8000/health
```

Services: `api` (port 8000), `worker`, `redis`.

## Tests

```bash
cd backend
uv sync
uv run ruff check .
uv run pytest
```

## Assumptions

- `.env` is required by compose; `REDIS_URL` and `UPLOAD_DIR` are overridden in compose for container paths.
