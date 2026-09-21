import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import config as _config  # Load .env before resolving storage paths.

ROOT = Path(os.getenv("DOCRAFT_DATA_DIR", Path(__file__).resolve().parent / "data"))
DB_PATH = ROOT / "docraft.db"
FILES = ROOT / "files"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    FILES.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS documents (
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          filename TEXT NOT NULL, media_type TEXT NOT NULL, size INTEGER NOT NULL, file_path TEXT NOT NULL,
          status TEXT NOT NULL, error TEXT, markdown TEXT, blocks TEXT NOT NULL DEFAULT '[]',
          result TEXT, groundings TEXT NOT NULL DEFAULT '{}', validation TEXT NOT NULL DEFAULT '[]',
          schema_id TEXT REFERENCES schemas(id), approved_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS schemas (
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          name TEXT NOT NULL, version INTEGER NOT NULL, json_schema TEXT NOT NULL,
          created_at TEXT NOT NULL, UNIQUE(project_id, name, version)
        );
        CREATE TABLE IF NOT EXISTS corrections (
          id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          path TEXT NOT NULL, old_value TEXT, new_value TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, action TEXT NOT NULL,
          resource_type TEXT NOT NULL, resource_id TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
        );
        """)
        columns = {row[1] for row in db.execute("PRAGMA table_info(documents)")}
        if "schema_id" not in columns:
            db.execute("ALTER TABLE documents ADD COLUMN schema_id TEXT REFERENCES schemas(id)")


@contextmanager
def connect():
    ROOT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    finally:
        db.close()


def decode(row, fields=()):
    value = dict(row)
    for field in fields:
        if value.get(field) is not None:
            value[field] = json.loads(value[field])
    return value


def audit(db, project_id, action, resource_type, resource_id, detail=None):
    db.execute(
        "INSERT INTO audit_log(project_id,action,resource_type,resource_id,detail,created_at) VALUES(?,?,?,?,?,?)",
        (project_id, action, resource_type, resource_id, json.dumps(detail or {}), now()),
    )
