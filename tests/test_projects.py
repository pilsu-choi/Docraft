"""PostgreSQL integration coverage for the project workspace API."""

import io
import time
from urllib.parse import quote

import openpyxl
from fastapi.testclient import TestClient

from backend.db import connect
from backend.main import app


client = TestClient(app)
DEFINITION = {"type": "object", "properties": {"name": {"type": "string"}}}


def project(name: str) -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(project_id: str, text: bytes = b"name: synthetic fixture\n") -> str:
    response = client.post(
        f"/api/projects/{project_id}/documents",
        files={"files": ("fixture.txt", io.BytesIO(text), "text/plain")},
    )
    assert response.status_code == 202, response.text
    return response.json()[0]["id"]


def wait_for(document_id: str, *statuses: str) -> dict:
    until = time.monotonic() + 3
    while time.monotonic() < until:
        response = client.get(f"/api/documents/{document_id}")
        assert response.status_code == 200
        value = response.json()
        if value["status"] in statuses:
            return value
        time.sleep(0.01)
    raise AssertionError(f"document did not reach {statuses}")


def schema(project_id: str, name: str = "record") -> dict:
    response = client.post(f"/api/projects/{project_id}/schemas", json={"name": name, "json_schema": DEFINITION})
    assert response.status_code == 201, response.text
    return response.json()


def test_project_rename_and_delete_cascade_in_postgresql():
    project_id = project("before")
    document_id = upload(project_id)
    wait_for(document_id, "parsed")
    schema_id = schema(project_id)["id"]

    renamed = client.patch(f"/api/projects/{project_id}", json={"name": "after", "description": "isolated"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "after"

    deleted = client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    with connect() as db:
        assert db.execute("SELECT id FROM documents WHERE id=?", (document_id,)).fetchone() is None
        assert db.execute("SELECT id FROM schemas WHERE id=?", (schema_id,)).fetchone() is None


def test_schema_versions_are_project_scoped_and_used_version_cannot_be_deleted(monkeypatch):
    first, second = project("first"), project("second")
    first_v1, second_v1 = schema(first, "invoice"), schema(second, "invoice")
    first_v2 = client.patch(f"/api/schemas/{first_v1['id']}", json={"name": "invoice", "json_schema": DEFINITION})
    assert first_v2.status_code == 201, first_v2.text
    assert (first_v1["version"], second_v1["version"], first_v2.json()["version"]) == (1, 1, 2)
    assert len(client.get(f"/api/projects/{first}/schemas").json()) == 2
    assert client.delete(f"/api/schemas/{first_v1['id']}").status_code == 204

    document_id = upload(first)
    wait_for(document_id, "parsed")
    # The worker is deterministic here; this test exercises the API's reference guard.
    monkeypatch.setattr("backend.main.engine.extract", lambda _schema, _blocks, _source=None: ({"name": "fixture"}, {"name": {"confidence": 1, "page": None, "bbox": None, "source_text": "name: fixture"}}))
    assert client.post(f"/api/documents/{document_id}/extract", json={"schema_id": first_v2.json()["id"]}).status_code == 202
    wait_for(document_id, "completed")
    assert client.delete(f"/api/schemas/{first_v2.json()['id']}").status_code == 409


def test_schema_generation_requires_a_parsed_same_project_reference(monkeypatch):
    first, second = project("generation first"), project("generation second")
    no_reference = client.post(f"/api/projects/{first}/schemas/generate", json={"prompt": ""})
    assert no_reference.status_code == 422

    other_document = upload(second)
    wait_for(other_document, "parsed")
    assert client.post(
        f"/api/projects/{first}/schemas/generate", json={"prompt": "", "document_id": other_document}
    ).status_code == 409

    document_id = upload(first)
    parsed = wait_for(document_id, "parsed")
    seen = {}

    def generate(prompt, documents):
        seen.update(prompt=prompt, documents=documents)
        return DEFINITION

    monkeypatch.setattr("backend.main.engine.generate_schema_from_documents", generate)
    response = client.post(
        f"/api/projects/{first}/schemas/generate",
        json={"prompt": "", "document_ids": [document_id], "name": "from parsed text"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["name"] == "from parsed text"
    assert seen["prompt"] == ""
    assert seen["documents"][0]["id"] == document_id
    assert parsed["markdown"] in seen["documents"][0]["markdown"]


def test_batch_extract_explicit_ids_skip_other_project_and_unknown(monkeypatch):
    monkeypatch.setattr("backend.main.engine.extract", lambda _schema, _blocks, _source=None: ({"name": "fixture"}, {}))
    project_id, other_id = project("batch-explicit"), project("batch-other")
    doc_a = upload(project_id); wait_for(doc_a, "parsed")
    doc_b = upload(project_id); wait_for(doc_b, "parsed")
    other_doc = upload(other_id); wait_for(other_doc, "parsed")
    schema_id = schema(project_id)["id"]

    response = client.post(
        f"/api/projects/{project_id}/extract",
        json={"schema_id": schema_id, "document_ids": [doc_a, other_doc, "missing-id"]},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["queued"] == [doc_a]
    reasons = {item["id"]: item["reason"] for item in body["skipped"]}
    assert reasons[other_doc] == "다른 프로젝트의 문서입니다."
    assert reasons["missing-id"] == "문서를 찾을 수 없습니다."
    assert doc_b not in body["queued"]
    wait_for(doc_a, "completed", "needs_review")


def test_batch_extract_default_scope_covers_project_and_skips_unparsed(monkeypatch):
    monkeypatch.setattr("backend.main.engine.extract", lambda _schema, _blocks, _source=None: ({"name": "fixture"}, {}))
    project_id = project("batch-default")
    ready_doc = upload(project_id); wait_for(ready_doc, "parsed")
    stuck_doc = upload(project_id); wait_for(stuck_doc, "parsed")
    with connect() as db:
        db.execute("UPDATE documents SET status='parsing' WHERE id=?", (stuck_doc,))
    schema_id = schema(project_id)["id"]

    response = client.post(f"/api/projects/{project_id}/extract", json={"schema_id": schema_id})
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["queued"] == [ready_doc]
    reasons = {item["id"]: item["reason"] for item in body["skipped"]}
    assert reasons[stuck_doc] == "파싱 완료 후 추출할 수 있습니다."
    wait_for(ready_doc, "completed", "needs_review")


def test_batch_extract_rejects_schema_from_another_project():
    project_id, other_id = project("batch-mismatch"), project("batch-mismatch-other")
    doc_id = upload(project_id); wait_for(doc_id, "parsed")
    other_schema_id = schema(other_id, "other")["id"]
    response = client.post(f"/api/projects/{project_id}/extract", json={"schema_id": other_schema_id})
    assert response.status_code == 409


def test_project_export_json_csv_and_schema_filter(monkeypatch):
    monkeypatch.setattr("backend.main.engine.extract", lambda _schema, _blocks, _source=None: ({"name": "A"}, {}))
    project_id = project("export project")
    schema_a = schema(project_id, "schema-a")["id"]
    schema_b = schema(project_id, "schema-b")["id"]

    doc_a = upload(project_id); wait_for(doc_a, "parsed")
    client.post(f"/api/documents/{doc_a}/extract", json={"schema_id": schema_a})
    wait_for(doc_a, "completed", "needs_review")

    doc_b = upload(project_id); wait_for(doc_b, "parsed")
    client.post(f"/api/documents/{doc_b}/extract", json={"schema_id": schema_b})
    wait_for(doc_b, "completed", "needs_review")

    not_extracted = upload(project_id); wait_for(not_extracted, "parsed")

    all_json = client.get(f"/api/projects/{project_id}/export?format=json")
    assert all_json.status_code == 200
    assert {item["document_id"] for item in all_json.json()} == {doc_a, doc_b}

    filtered = client.get(f"/api/projects/{project_id}/export?format=json&schema_id={schema_a}")
    assert [item["document_id"] for item in filtered.json()] == [doc_a]

    csv_response = client.get(f"/api/projects/{project_id}/export?format=csv")
    assert csv_response.status_code == 200
    lines = csv_response.text.strip().splitlines()
    assert lines[0] == "document_id,filename,status,name"
    assert len(lines) == 3

    xlsx_response = client.get(f"/api/projects/{project_id}/export?format=xlsx")
    assert xlsx_response.status_code == 200
    workbook = openpyxl.load_workbook(io.BytesIO(xlsx_response.content))
    assert workbook["result"].max_row == 3

    empty = client.get(f"/api/projects/{project_id}/export?format=csv&schema_id=does-not-exist")
    assert empty.text.strip().splitlines() == ["document_id,filename,status"]

    assert client.get("/api/projects/does-not-exist/export").status_code == 404


def test_project_export_filename_handles_korean_project_names():
    project_id = project("한글 프로젝트")
    response = client.get(f"/api/projects/{project_id}/export?format=json")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "filename*=UTF-8''" in disposition
    assert quote("한글 프로젝트.json") in disposition


def test_schema_generation_rejects_failed_or_unparsed_reference():
    project_id = project("generation state")
    response = client.post(
        f"/api/projects/{project_id}/documents",
        files={"files": ("broken.pdf", io.BytesIO(b"not a PDF"), "application/pdf")},
    )
    document_id = response.json()[0]["id"]
    wait_for(document_id, "failed")
    generated = client.post(
        f"/api/projects/{project_id}/schemas/generate", json={"prompt": "", "document_id": document_id}
    )
    assert generated.status_code == 409
