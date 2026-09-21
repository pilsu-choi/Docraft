"""Safety checks for the explicit SQLite-to-PostgreSQL migration."""

import os
import sqlite3

import pytest

from backend.db import connect, now
from scripts.migrate_sqlite_to_postgres import migrate


def source_db(tmp_path, project_id="old-project", name="old project"):
    path = tmp_path / "old-docraft.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT, description TEXT, created_at TEXT, updated_at TEXT)")
        db.execute("INSERT INTO projects VALUES (?, ?, '', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')", (project_id, name))
    return path


def empty_target():
    with connect() as db:
        db.execute("TRUNCATE audit_log, corrections, documents, schemas, projects RESTART IDENTITY CASCADE")


def test_migration_accepts_audit_only_target_and_preserves_it(tmp_path):
    empty_target()
    with connect() as db:
        db.execute(
            "INSERT INTO audit_log(project_id,action,resource_type,resource_id,detail,created_at) VALUES(?,?,?,?,?,?)",
            (None, "health", "system", "existing", "{}", now()),
        )
    migrate(source_db(tmp_path), os.environ["DATABASE_URL"])
    with connect() as db:
        assert db.execute("SELECT name FROM projects WHERE id=?", ("old-project",)).fetchone()["name"] == "old project"
        assert db.execute("SELECT COUNT(*) AS count FROM audit_log").fetchone()["count"] == 1


def test_migration_rejects_a_target_with_business_data(tmp_path):
    empty_target()
    with connect() as db:
        db.execute(
            "INSERT INTO projects VALUES(?,?,?,?,?)",
            ("already-there", "existing", "", now(), now()),
        )
    with pytest.raises(SystemExit, match="업무 테이블"):
        migrate(source_db(tmp_path, "should-not-copy"), os.environ["DATABASE_URL"])
    with connect() as db:
        assert db.execute("SELECT id FROM projects WHERE id=?", ("should-not-copy",)).fetchone() is None


def test_migration_removes_postgresql_incompatible_nul_from_legacy_text(tmp_path):
    empty_target()
    migrate(source_db(tmp_path, name="legacy\x00project"), os.environ["DATABASE_URL"])
    with connect() as db:
        assert db.execute("SELECT name FROM projects WHERE id=?", ("old-project",)).fetchone()["name"] == "legacyproject"
