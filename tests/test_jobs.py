import sys
import time
import types

import pytest

from backend import jobs
from backend.db import connect
from backend.main import heartbeat, recover, run_extract, run_parse
from tests.test_api import project, schema, upload, wait_for


def test_tasks_are_registered_and_inline_is_default(monkeypatch):
    monkeypatch.delenv("QUEUE_BACKEND", raising=False)
    assert set(jobs.TASKS) == {"parse", "extract"}
    assert jobs.backend() is jobs._inline


def test_unknown_backend_is_rejected(monkeypatch):
    monkeypatch.setenv("QUEUE_BACKEND", "kafka")
    with pytest.raises(RuntimeError, match="kafka"):
        jobs.enqueue("parse", "missing")


def test_duplicate_delivery_is_skipped_by_db_claim():
    document_id = upload(project("claim"))
    parsed = wait_for(document_id, "parsed")
    run_parse(document_id)  # Redelivered message: document is no longer queued.
    run_extract(document_id, "any-schema")
    with connect() as db:
        row = db.execute("SELECT status,updated_at FROM documents WHERE id=?", (document_id,)).fetchone()
    assert (row["status"], row["updated_at"]) == ("parsed", parsed["updated_at"])


def test_celery_backend_sends_namespaced_task(monkeypatch):
    sent, registered = [], []

    class FakeCelery:
        def __init__(self, main, broker, backend):
            self.conf = types.SimpleNamespace(update=lambda **options: sent.append(("conf", options)))

        def task(self, name, **options):
            registered.append((name, options["max_retries"]))
            return lambda fn: fn

        def send_task(self, name, args, queue):
            sent.append((name, args, queue))

    monkeypatch.setitem(sys.modules, "celery", types.SimpleNamespace(Celery=FakeCelery))
    monkeypatch.setenv("QUEUE_BACKEND", "celery")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://shared:6379/3")
    jobs.celery_app.cache_clear()
    try:
        jobs.enqueue("extract", "doc-1", "schema-1")
    finally:
        jobs.celery_app.cache_clear()
    conf = sent[0][1]
    assert conf["task_default_queue"] == "docraft" and conf["task_acks_late"]
    assert conf["broker_transport_options"] == {"global_keyprefix": "docraft:", "visibility_timeout": jobs.LEASE}
    assert sorted(registered) == [("docraft.extract", 3), ("docraft.parse", 3)]
    assert sent[1] == ("docraft.extract", ("doc-1", "schema-1"), "docraft")


def set_status(document_id, status, updated_at):
    with connect() as db:
        db.execute("UPDATE documents SET status=?,updated_at=? WHERE id=?", (status, updated_at, document_id))


def test_stale_job_is_taken_over_but_live_one_is_not():
    document_id = upload(project("lease"))
    wait_for(document_id, "parsed")
    set_status(document_id, "parsing", "2000-01-01T00:00:00+00:00")  # Worker died long ago.
    run_parse(document_id)
    assert wait_for(document_id, "parsed")["status"] == "parsed"
    live = "2999-01-01T00:00:00+00:00"  # A heartbeating job.
    set_status(document_id, "parsing", live)
    run_parse(document_id)
    with connect() as db:
        assert db.execute("SELECT updated_at FROM documents WHERE id=?", (document_id,)).fetchone()["updated_at"] == live


def test_recover_resumes_queued_and_stale_jobs():
    project_id = project("recover")
    lost_parse, stale_extract = upload(project_id), upload(project_id)
    wait_for(lost_parse, "parsed"), wait_for(stale_extract, "parsed")
    schema_id = schema(project_id)
    with connect() as db:
        db.execute("UPDATE documents SET status='queued',markdown=NULL WHERE id=?", (lost_parse,))  # Inline job lost on restart.
        db.execute("UPDATE documents SET status='extracting',schema_id=?,updated_at='2000-01-01T00:00:00+00:00' WHERE id=?", (schema_id, stale_extract))
    recover()
    assert wait_for(lost_parse, "parsed")["status"] == "parsed"
    assert wait_for(stale_extract, "completed")["schema_id"] == schema_id


def test_heartbeat_refreshes_running_job(monkeypatch):
    document_id = upload(project("heartbeat"))
    wait_for(document_id, "parsed")
    set_status(document_id, "extracting", "2000-01-01T00:00:00+00:00")
    monkeypatch.setattr(jobs, "LEASE", 0.15)
    with heartbeat(document_id): time.sleep(0.2)
    with connect() as db:
        assert db.execute("SELECT updated_at FROM documents WHERE id=?", (document_id,)).fetchone()["updated_at"] > "2001"
