# GET /parsers

Lists the parsers selectable in `POST /documents` (the legacy `gemini` alias is accepted but not listed) and the upload limits from settings.

```bash
curl localhost:8000/parsers
# {"parsers": ["pypdf", "llm"], "default": "pypdf", "max_file_size_mb": 20, "max_files_per_upload": 10}
```

Always `200`. Code: `backend/app/main.py`.
