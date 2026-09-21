"""One-time, explicit SQLite metadata migration; original database and files remain untouched."""

import argparse
import os
import sqlite3
from pathlib import Path

import psycopg
from psycopg import sql

from backend.db import init_db


TABLES = ("projects", "schemas", "documents", "corrections", "audit_log")


def migrate(source: Path, url: str) -> None:
    if not source.is_file():
        raise SystemExit("SQLite 파일을 찾을 수 없습니다.")
    os.environ["DATABASE_URL"] = url
    init_db()
    with sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True) as old, psycopg.connect(url) as new:
        for table in TABLES[:-1]:
            if new.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier(table))).fetchone():
                raise SystemExit("대상 PostgreSQL 업무 테이블이 비어 있지 않습니다. 중복 이관을 중지합니다.")
        for table in TABLES:
            columns = [row[1] for row in old.execute(f"PRAGMA table_info({table})")]
            if not columns:
                continue
            if table == "audit_log":
                columns.remove("id")  # Retain existing PostgreSQL audit rows and allocate new IDs.
            rows = old.execute(f"SELECT {','.join(columns)} FROM {table}").fetchall()
            # PostgreSQL rejects embedded NUL in text; preserve every other character.
            rows = [tuple(value.replace("\x00", "") if isinstance(value, str) else value for value in row) for row in rows]
            statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(table),
                sql.SQL(",").join(map(sql.Identifier, columns)),
                sql.SQL(",").join(sql.Placeholder() for _ in columns),
            )
            if rows:
                with new.cursor() as cursor:
                    cursor.executemany(statement, rows)
            print(f"{table}: {len(rows)}건")
        for table in ("corrections", "audit_log"):
            new.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE((SELECT MAX(id) FROM "
                + table + "), 1), (SELECT COUNT(*) > 0 FROM " + table + "))",
                (table,),
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="기존 docraft.db 경로")
    parser.add_argument("--url", default=os.getenv("DATABASE_URL", "postgresql://docraft:docraft@127.0.0.1:5433/docraft"))
    args = parser.parse_args()
    migrate(args.source, args.url)
