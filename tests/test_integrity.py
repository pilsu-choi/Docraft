"""Generation fencing and partial results: real DB state, barrier-controlled workers, no model calls."""
import csv
import io
import json
import threading
import time

import openpyxl
import pytest

from backend import engine, jobs, main, reprocess
from backend.db import connect
from tests.test_api import client, project, schema, upload, wait_for


def row(document_id):
    with connect() as db:
        return dict(db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone())


def prepared():
    project_id = project("integrity")
    document_id = upload(project_id)
    wait_for(document_id, "parsed")
    return project_id, document_id, schema(project_id)


def thread_call(fn):
    errors = []
    def run():
        try: fn()
        except BaseException as exc: errors.append(exc)
    thread = threading.Thread(target=run)
    thread.start()
    return thread, errors


@pytest.mark.parametrize("old_fails", [False, True])
@pytest.mark.parametrize("takeover", [False, True])
def test_old_parse_cannot_overwrite_retry_or_lease_takeover(monkeypatch, old_fails, takeover):
    _, document_id, _ = prepared()
    ready, release = threading.Event(), threading.Event()
    calls = []
    def parse(*args):
        calls.append(1)
        if len(calls) == 1:
            ready.set()
            assert release.wait(5)
            if old_fails: raise RuntimeError("old failure")
            return "OLD", []
        return "NEW", []
    monkeypatch.setattr(main, "parse", parse)
    monkeypatch.setattr(jobs, "enqueue", lambda *a, **k: None)
    with connect() as db: db.execute("UPDATE documents SET status='queued' WHERE id=?", (document_id,))
    thread, errors = thread_call(lambda: main.run_parse(document_id))
    try:
        assert ready.wait(5)
        if takeover:
            with connect() as db: db.execute("UPDATE documents SET updated_at='2000-01-01' WHERE id=?", (document_id,))
            generation = ""
        else:
            assert client.post(f"/api/documents/{document_id}/parse").status_code == 202
            generation = row(document_id)["job_generation"]
        main.run_parse(document_id, generation)
        assert row(document_id)["markdown"] == "NEW"
    finally:
        release.set(); thread.join(5)
    assert not thread.is_alive() and not errors
    current = row(document_id)
    assert current["status"] == "parsed" and current["markdown"] == "NEW" and current["error"] is None


@pytest.mark.parametrize("stage", ["extract", "validate"])
@pytest.mark.parametrize("old_fails", [False, True])
def test_old_extract_and_validation_cannot_write_after_reparse(monkeypatch, stage, old_fails):
    _, document_id, schema_id = prepared()
    ready, release = threading.Event(), threading.Event()
    def extract(*args, **kwargs):
        if stage == "extract":
            ready.set(); assert release.wait(5)
            if old_fails: raise RuntimeError("old extract failure")
        return {"hospital": "ABC Hospital", "total_amount": 120000}, {}
    def recover(image, schema, blocks, result, **kwargs):
        if stage == "validate":
            ready.set(); assert release.wait(5)
            if old_fails: raise RuntimeError("old recovery failure")
        return result, {}, {}, {}
    monkeypatch.setattr(engine, "extract", extract)
    monkeypatch.setattr(reprocess, "run", recover)
    monkeypatch.setattr(jobs, "enqueue", lambda *a, **k: None)
    assert client.post(f"/api/documents/{document_id}/extract", json={"schema_id": schema_id}).status_code == 202
    generation = row(document_id)["job_generation"]
    thread, errors = thread_call(lambda: main.run_extract(document_id, schema_id, generation))
    try:
        assert ready.wait(5)
        assert client.post(f"/api/documents/{document_id}/parse").status_code == 202
        new_generation = row(document_id)["job_generation"]
        main.run_parse(document_id, new_generation)
    finally:
        release.set(); thread.join(5)
    assert not thread.is_alive() and not errors
    current = row(document_id)
    assert current["status"] == "parsed" and current["result"] is None and current["error"] is None


def test_old_delivery_and_heartbeat_cannot_claim_or_refresh_new_generation(monkeypatch):
    _, document_id, _ = prepared()
    with connect() as db:
        db.execute("UPDATE documents SET status='queued' WHERE id=?", (document_id,))
        old_owner = main.claim(db, document_id, "parsing")
    monkeypatch.setattr(jobs, "enqueue", lambda *a, **k: None)
    client.post(f"/api/documents/{document_id}/parse")
    main.run_parse(document_id)  # Old broker message has the old generation.
    current = row(document_id)
    assert current["status"] == "queued"
    monkeypatch.setattr(jobs, "LEASE", 0.09)
    with connect() as db:
        db.execute("UPDATE documents SET status='parsing',job_owner='new-owner',updated_at='2000-01-01' WHERE id=?", (document_id,))
    with main.heartbeat(document_id, old_owner): time.sleep(0.15)
    assert row(document_id)["updated_at"] == "2000-01-01"


@pytest.mark.parametrize("queued_path", ["document", "batch"])
def test_queued_extraction_cannot_be_approved_or_edited(monkeypatch, queued_path):
    project_id, document_id, schema_id = prepared()
    client.post(f"/api/documents/{document_id}/extract", json={"schema_id": schema_id})
    wait_for(document_id, "completed")
    monkeypatch.setattr(jobs, "enqueue", lambda *a, **k: None)
    path = f"/api/documents/{document_id}/extract" if queued_path == "document" else f"/api/projects/{project_id}/extract"
    assert client.post(path, json={"schema_id": schema_id, "document_ids": [document_id]}).status_code == 202
    assert client.post(f"/api/documents/{document_id}/approve").status_code == 409
    assert client.patch(f"/api/documents/{document_id}/review", json={"path": "/hospital", "value": "old"}).status_code == 409
    current = row(document_id)
    assert current["status"] == "queued" and current["result"] is None and current["approved_at"] is None


def test_new_parse_clears_prior_cancel_request(monkeypatch):
    _, document_id, _ = prepared()
    monkeypatch.setattr(jobs, "enqueue", lambda *a, **k: None)
    with connect() as db: db.execute("UPDATE documents SET status='parsing',cancel_requested=TRUE WHERE id=?", (document_id,))
    client.post(f"/api/documents/{document_id}/parse")
    current = row(document_id)
    assert current["cancel_requested"] is False
    main.run_parse(document_id, current["job_generation"])
    assert row(document_id)["status"] == "parsed"


@pytest.mark.parametrize("value", ["=1+1", "+SUM(1,2)", "-1+2", "@SUM(1,2)", "  =1", "\t=1", "\r=1", "\n=1", "\x01=1", "-123", "+12"])
def test_spreadsheet_strings_and_headers_are_literal(value):
    response = main.table_response([{value: value, "number": -123.5}], "safe", "csv")
    cells = list(csv.reader(io.StringIO(response.body.decode())))
    assert cells[0][0] == "'" + value and cells[1][0] == "'" + value
    assert cells[1][1] == "-123.5"
    response = main.table_response([{value: value, "number": -123.5}], "safe", "xlsx")
    if response:
        value = value.replace("\x01", "\ufffd")
        sheet = openpyxl.load_workbook(io.BytesIO(response.body), data_only=False).active
        assert sheet["A1"].value == value and sheet["A1"].data_type == "s"
        assert sheet["A2"].value == value and sheet["A2"].data_type == "s"
        assert sheet["B2"].value == -123.5 and sheet["B2"].data_type == "n"


def test_partial_result_survives_review_is_not_completed_or_approved_and_is_exported(monkeypatch):
    project_id, document_id, schema_id = prepared()
    completeness = {"partial": True, "pages": [1, 2, 3], "successful_pages": [1, 3], "failed_pages": [2],
                    "tables": {"items": {"successful_pages": [1, 3], "failed_pages": [2]}}}
    def extract(*args, **kwargs):
        kwargs["completeness"].update(completeness)
        return {"hospital": "ABC Hospital", "total_amount": 120000}, {}
    monkeypatch.setattr(engine, "extract", extract)
    monkeypatch.setattr(reprocess, "run", lambda image, schema, blocks, result, **kwargs: (result, {}, {}, {}))
    monkeypatch.setattr(jobs, "enqueue", lambda *a, **k: None)
    client.post(f"/api/documents/{document_id}/extract", json={"schema_id": schema_id})
    main.run_extract(document_id, schema_id, row(document_id)["job_generation"])
    doc = client.get(f"/api/documents/{document_id}").json()
    stored = {**completeness, "integrity": {"input": {}, "flags": [], "lossy_pages": []}}  # 입력 무결성 요약이 완결성 정보에 함께 남는다
    assert doc["status"] == "needs_review" and doc["completeness"] == stored
    assert any(issue["code"] == "partial_extraction" for issue in doc["validation"])
    corrected = client.patch(f"/api/documents/{document_id}/review", json={"path": "/hospital", "value": "ABC Hospital"})
    assert corrected.status_code == 200
    assert any(issue["code"] == "partial_extraction" for issue in corrected.json()["validation"])
    assert client.post(f"/api/documents/{document_id}/approve").status_code == 422
    assert next(d for d in client.get(f"/api/projects/{project_id}/documents").json() if d["id"] == document_id)["completeness"] == stored
    single = client.get(f"/api/documents/{document_id}/export?format=json").json()
    assert single["completeness"] == stored and single["result"] == doc["result"]
    group = client.get(f"/api/projects/{project_id}/export?format=json").json()
    assert group[0]["completeness"] == stored
    for path in (f"/api/documents/{document_id}/export", f"/api/projects/{project_id}/export"):
        cells = list(csv.DictReader(io.StringIO(client.get(path + "?format=csv").text)))
        assert cells[0]["_docraft.partial"] == "True" and json.loads(cells[0]["_docraft.completeness"]) == stored
        sheet = openpyxl.load_workbook(io.BytesIO(client.get(path + "?format=xlsx").content)).active
        assert "_docraft.partial" in [cell.value for cell in sheet[1]]
