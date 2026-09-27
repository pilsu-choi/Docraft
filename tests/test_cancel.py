"""운영자의 긴급 중지: 문서 잡 취소(`POST /api/documents/{id}/cancel`)와 전체 취소(`POST /api/admin/cancel-all`)."""

import threading
import types

from backend import engine, jobs, verify
from backend import main
from backend.db import connect, now
from backend.main import app, run_extract, run_parse
from fastapi.testclient import TestClient

from test_api import project, schema, upload, wait_for
from test_read import post_read
from test_verify import _image

client = TestClient(app)


def status_of(document_id):
    with connect() as db:
        return dict(db.execute("SELECT status,cancel_requested,result FROM documents WHERE id=?", (document_id,)).fetchone())


# --- 잡 단계 경계의 협조적 취소(run_parse/run_extract) -----------------------


def test_run_parse_marks_canceled_instead_of_parsed_when_cancel_requested():
    document_id = upload(project("cancel-parse"))
    wait_for(document_id, "parsed")
    with connect() as db:
        db.execute("UPDATE documents SET status='queued',cancel_requested=TRUE,updated_at=? WHERE id=?", (now(), document_id))

    run_parse(document_id)

    row = status_of(document_id)
    assert row["status"] == "canceled" and row["cancel_requested"] is False


def test_run_extract_stops_before_writing_a_result_when_cancelled_up_front():
    project_id = project("cancel-extract-early")
    document_id = upload(project_id)
    wait_for(document_id, "parsed")
    schema_id = schema(project_id)
    with connect() as db:
        db.execute("UPDATE documents SET status='queued',schema_id=?,cancel_requested=TRUE,updated_at=? WHERE id=?", (schema_id, now(), document_id))

    run_extract(document_id, schema_id)

    row = status_of(document_id)
    assert row["status"] == "canceled" and row["cancel_requested"] is False and row["result"] is None


def test_run_extract_stops_after_validate_when_cancelled_mid_run(monkeypatch):
    project_id = project("cancel-extract-late")
    document_id = upload(project_id)
    wait_for(document_id, "parsed")
    schema_id = schema(project_id)
    with connect() as db:
        db.execute("UPDATE documents SET status='queued',schema_id=?,updated_at=? WHERE id=?", (schema_id, now(), document_id))

    def cancel_mid_flight(result, json_schema, groundings):
        with connect() as db: db.execute("UPDATE documents SET cancel_requested=TRUE WHERE id=?", (document_id,))
        return []

    monkeypatch.setattr(engine, "validate", cancel_mid_flight)

    run_extract(document_id, schema_id)

    row = status_of(document_id)
    assert row["status"] == "canceled" and row["cancel_requested"] is False
    assert row["result"] is not None  # 첫 번째 경계(추출 뒤)는 지나 result가 저장됐다


# --- POST /api/documents/{id}/cancel ----------------------------------------


def test_cancel_route_cancels_a_queued_document(monkeypatch):
    monkeypatch.setattr(jobs, "enqueue", lambda *args, **kwargs: None)  # 잡을 넣지 않아 queued로 남는다
    document_id = upload(project("cancel-route-queued"))

    response = client.post(f"/api/documents/{document_id}/cancel")

    assert response.status_code == 200 and response.json()["status"] == "canceled"
    assert "cancel_requested" not in response.json()


def test_cancel_route_flags_a_running_document_without_stopping_it_immediately():
    document_id = upload(project("cancel-route-running"))
    wait_for(document_id, "parsed")
    with connect() as db: db.execute("UPDATE documents SET status='extracting',updated_at=? WHERE id=?", (now(), document_id))

    response = client.post(f"/api/documents/{document_id}/cancel")

    assert response.status_code == 200 and response.json()["status"] == "extracting"  # 다음 경계까지는 진행 중 표시 그대로
    assert status_of(document_id)["cancel_requested"] is True


def test_cancel_route_rejects_a_terminal_document():
    document_id = upload(project("cancel-route-terminal"))
    wait_for(document_id, "parsed")
    with connect() as db: db.execute("UPDATE documents SET status='completed',updated_at=? WHERE id=?", (now(), document_id))

    response = client.post(f"/api/documents/{document_id}/cancel")

    assert response.status_code == 409


def test_cancel_route_rejects_an_already_canceled_document():
    document_id = upload(project("cancel-route-already"))
    wait_for(document_id, "parsed")
    with connect() as db: db.execute("UPDATE documents SET status='canceled',updated_at=? WHERE id=?", (now(), document_id))

    response = client.post(f"/api/documents/{document_id}/cancel")

    assert response.status_code == 409


def test_cancel_route_returns_404_for_an_unknown_document():
    response = client.post("/api/documents/missing/cancel")

    assert response.status_code == 404


def test_dispatch_remembers_a_celery_task_id_for_later_revoke(monkeypatch):
    monkeypatch.setattr(jobs, "enqueue", lambda name, *args: types.SimpleNamespace(id="task-123"))

    main.dispatch("doc-x", "parse")

    assert main.TASK_IDS.pop("doc-x") == "task-123"


def test_cancel_route_revokes_the_tracked_task_id_and_forgets_it(monkeypatch):
    monkeypatch.setattr(jobs, "enqueue", lambda *args, **kwargs: None)
    document_id = upload(project("cancel-route-revoke"))
    main.TASK_IDS[document_id] = "task-abc"
    revoked = []
    monkeypatch.setattr(jobs, "revoke", lambda task_id: revoked.append(task_id))

    response = client.post(f"/api/documents/{document_id}/cancel")

    assert response.status_code == 200 and revoked == ["task-abc"]
    assert document_id not in main.TASK_IDS


# --- POST /api/admin/cancel-all ---------------------------------------------


def test_cancel_all_requires_confirm():
    assert client.post("/api/admin/cancel-all").status_code == 422


def test_cancel_all_cancels_queued_and_flags_running_documents(monkeypatch):
    monkeypatch.setattr(jobs, "enqueue", lambda *args, **kwargs: None)  # 두 문서 모두 상태를 손으로 고정한다
    project_id = project("cancel-all-docs")
    queued_id = upload(project_id, filename="queued.txt")
    running_id = upload(project_id, filename="running.txt")
    with connect() as db: db.execute("UPDATE documents SET status='extracting',updated_at=? WHERE id=?", (now(), running_id))

    response = client.post("/api/admin/cancel-all", params={"confirm": "true"})
    body = response.json()

    assert response.status_code == 200
    assert body["queued_canceled"] >= 1 and body["running_canceled"] >= 1
    assert status_of(queued_id)["status"] == "canceled"
    running_row = status_of(running_id)
    assert running_row["status"] == "extracting" and running_row["cancel_requested"] is True


def test_cancel_all_sets_every_inflight_read_call_and_it_returns_409(monkeypatch, tmp_path):
    ready = threading.Event()

    def fake_read(path, doc_type, only, cancel=None, with_groundings=False):
        ready.set()
        assert cancel.wait(5)
        raise verify.Cancelled(getattr(cancel, "reason", None))

    monkeypatch.setattr(verify, "read", fake_read)
    outcome = {}

    def call(): outcome["response"] = post_read(_image(tmp_path))

    thread = threading.Thread(target=call)
    thread.start()
    assert ready.wait(5)

    response = client.post("/api/admin/cancel-all", params={"confirm": "true"})
    thread.join(5)

    assert response.status_code == 200 and response.json()["inflight_canceled"] >= 1
    assert outcome["response"].status_code == 409
    assert client.get("/api/health").json()["verify_inflight"] == 0
