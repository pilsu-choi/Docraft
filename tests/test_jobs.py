import sys
import types

import pytest

from backend import jobs
from backend.db import connect
from backend.main import run_extract, run_parse
from tests.test_api import project, upload, wait_for


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
    assert conf["broker_transport_options"] == {"global_keyprefix": "docraft:"}
    assert sorted(registered) == [("docraft.extract", 3), ("docraft.parse", 3)]
    assert sent[1] == ("docraft.extract", ("doc-1", "schema-1"), "docraft")
