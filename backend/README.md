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

For an OpenAI-compatible extraction provider, set `AI_BASE_URL`, `AI_API_KEY`, and
`AI_MODEL`. Without these values, schema generation and extraction use the explicit
local label/value heuristic. Image OCR additionally requires the `tesseract` system
binary; its absence is reported as a retryable parse failure.

Production RBAC, webhooks, retention automation, SDKs, and OCR provider integration
are outside the P0 implementation.
