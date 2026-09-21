# Docraft backend

Run from the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn backend.main:app --reload
```

The OpenAPI document is available at `http://localhost:8000/docs`. Data defaults to
`backend/data`; set `DOCRAFT_DATA_DIR` to move it. Set `DOCRAFT_API_KEY` to require
an `X-API-Key` header. Uploads are limited to 25 MiB by default (`MAX_UPLOAD_BYTES`).

For an OpenAI-compatible extraction provider, set `AI_MODE=provider`, `AI_BASE_URL`,
`AI_API_KEY`, and `AI_VLM_MODEL` (`AI_MODEL` remains a compatibility alias). The app
loads `.env` automatically. Provider failures are exposed instead of silently using
heuristic output. Set `AI_MODE=local` explicitly for offline development. Parsing
defaults to existing libraries (`PARSE_PROVIDER=library`). Optional image/scanned
PDF OCR uses an externally hosted Paddle full layout service with `PARSE_PROVIDER=paddle`;
no local OCR model is installed.

Production RBAC, webhooks, retention automation, SDKs, and OCR provider operations
are outside the P0 implementation.
