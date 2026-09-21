"""A real PostgreSQL schema isolated for this pytest process."""

import atexit
import os
import tempfile
import uuid
from urllib.parse import quote

import psycopg


TEST_DATA_DIR = tempfile.mkdtemp(prefix="docraft-tests-")
TEST_SCHEMA = f"docraft_test_{uuid.uuid4().hex}"
TEST_DATABASE_URL = os.getenv(
    "DOCRAFT_TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://docraft:docraft@127.0.0.1:5433/docraft"),
)


def _schema_url(url: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}options={quote(f'-csearch_path={TEST_SCHEMA}')}"


with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as _admin:
    _admin.execute(f'CREATE SCHEMA "{TEST_SCHEMA}"')


@atexit.register
def _drop_test_schema():
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
        admin.execute(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE')


# backend.db resolves settings at import time. Keep uploads local and every
# request on the temporary PostgreSQL schema, never SQLite.
os.environ["DOCRAFT_DATA_DIR"] = TEST_DATA_DIR
os.environ["DATABASE_URL"] = _schema_url(TEST_DATABASE_URL)
os.environ.pop("DOCRAFT_API_KEY", None)
os.environ["AI_MODE"] = "local"
os.environ["PARSE_PROVIDER"] = "library"
os.environ["PADDLEOCR_LINES_URL"] = ""  # a developer .env must not switch line OCR on inside tests

from backend.db import init_db

init_db()
