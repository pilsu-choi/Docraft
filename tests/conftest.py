"""Shared isolated API test environment."""

import os
import tempfile

# backend.db resolves its paths at import time; set a process-local temp root
# before test modules import the application.
TEST_DATA_DIR = tempfile.mkdtemp(prefix="docraft-tests-")
os.environ["DOCRAFT_DATA_DIR"] = TEST_DATA_DIR
os.environ.pop("DOCRAFT_API_KEY", None)
os.environ["AI_MODE"] = "local"

# TestClient is intentionally module-scoped in test_api.py. Initialize the same
# application lifecycle state that uvicorn would initialize on startup.
from backend.db import init_db

init_db()
