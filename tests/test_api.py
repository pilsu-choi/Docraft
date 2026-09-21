import io
import time

from fastapi.testclient import TestClient

from backend.db import connect
from backend.main import app


client = TestClient(app)


def wait_for(document_id, *statuses):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get(f"/api/documents/{document_id}")
        assert response.status_code == 200
        document = response.json()
        if document["status"] in statuses:
            return document
        time.sleep(0.01)
    raise AssertionError(f"document did not reach {statuses}: {document}")


def project(name):
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def upload(project_id, filename="invoice.txt", content=b"Hospital: ABC Hospital\nTotal Amount: 120000\n"):
    response = client.post(
        f"/api/projects/{project_id}/documents",
        files={"files": (filename, io.BytesIO(content), "text/plain")},
    )
    assert response.status_code == 202, response.text
    return response.json()[0]["id"]


def schema(project_id, name="invoice"):
    response = client.post(
        f"/api/projects/{project_id}/schemas",
        json={
            "name": name,
            "json_schema": {
                "type": "object",
                "properties": {
                    "hospital": {"type": "string", "title": "Hospital"},
                    "total_amount": {"type": "number", "title": "Total Amount"},
                },
                "required": ["hospital", "total_amount"],
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_upload_parse_extract_grounding_and_export():
    project_id = project("pipeline")
    document_id = upload(project_id)
    parsed = wait_for(document_id, "parsed")
    assert "Hospital: ABC Hospital" in parsed["markdown"]
    assert parsed["blocks"]

    schema_id = schema(project_id)
    response = client.post(f"/api/documents/{document_id}/extract", json={"schema_id": schema_id})
    assert response.status_code == 202
    result = wait_for(document_id, "completed")
    assert result["result"] == {"hospital": "ABC Hospital", "total_amount": 120000.0}
    grounding = next(item for item in result["groundings"] if item["path"] == "hospital")
    assert grounding["text"]
    assert grounding["page"] is None

    exported = client.get(f"/api/documents/{document_id}/export?format=json")
    assert exported.status_code == 200
    assert '"hospital": "ABC Hospital"' in exported.text
    csv = client.get(f"/api/documents/{document_id}/export?format=csv")
    assert csv.status_code == 200
    assert "hospital,total_amount" in csv.text


def test_project_schema_mismatch_is_rejected():
    first, second = project("first"), project("second")
    document_id = upload(first)
    wait_for(document_id, "parsed")
    other_schema = schema(second, "other")
    response = client.post(f"/api/documents/{document_id}/extract", json={"schema_id": other_schema})
    assert response.status_code == 409


def test_unknown_schema_is_a_client_error():
    project_id = project("unknown-schema")
    document_id = upload(project_id)
    wait_for(document_id, "parsed")
    response = client.post(
        f"/api/documents/{document_id}/extract",
        json={"schema_id": "does-not-exist"},
    )
    assert response.status_code in {404, 409}


def test_invalid_schema_is_rejected_with_validation_error():
    project_id = project("invalid-schema")
    response = client.post(
        f"/api/projects/{project_id}/schemas",
        json={"name": "bad", "json_schema": {"type": "not-a-json-schema-type"}},
    )
    assert response.status_code == 422


def test_correction_is_persisted_and_recorded():
    project_id = project("correction")
    document_id = upload(project_id)
    wait_for(document_id, "parsed")
    schema_id = schema(project_id, "correction-schema")
    client.post(f"/api/documents/{document_id}/extract", json={"schema_id": schema_id})
    wait_for(document_id, "completed")

    response = client.patch(
        f"/api/documents/{document_id}/review",
        json={"path": "/hospital", "value": "XYZ Hospital"},
    )
    assert response.status_code == 200, response.text
    corrected = response.json()
    assert corrected["result"]["hospital"] == "XYZ Hospital"
    assert corrected["corrections"][-1]["path"] == "/hospital"
    assert corrected["status"] == "needs_review"
    approved = client.post(f"/api/documents/{document_id}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "completed"


def test_unsupported_upload_and_invalid_export_are_rejected():
    project_id = project("validation")
    response = client.post(
        f"/api/projects/{project_id}/documents",
        files={"files": ("malware.exe", io.BytesIO(b"no"), "application/octet-stream")},
    )
    assert response.status_code == 415

    document_id = upload(project_id)
    wait_for(document_id, "parsed")
    invalid = client.get(f"/api/documents/{document_id}/export?format=xml")
    assert invalid.status_code == 409  # no extraction result yet


def test_parse_failure_is_visible_as_async_failed_status():
    project_id = project("failed-parse")
    document_id = upload(project_id, "broken.pdf", b"not a PDF")
    failed = wait_for(document_id, "failed")
    assert failed["error"]


def test_document_list_is_lightweight():
    project_id = project("lightweight-list")
    document_id = upload(project_id)
    wait_for(document_id, "parsed")
    response = client.get(f"/api/projects/{project_id}/documents")
    assert response.status_code == 200
    listed = response.json()[0]
    assert "markdown" not in listed and "blocks" not in listed and "groundings" not in listed
    assert "result" in listed and "validation" in listed


def test_document_delete_removes_row_and_file_but_not_while_busy():
    project_id = project("delete-document")
    document_id = upload(project_id)
    wait_for(document_id, "parsed")

    with connect() as db:
        db.execute("UPDATE documents SET status='extracting' WHERE id=?", (document_id,))
    busy = client.delete(f"/api/documents/{document_id}")
    assert busy.status_code == 409, busy.text
    assert busy.json()["detail"] == "처리 중인 문서는 삭제할 수 없습니다."
    with connect() as db:
        db.execute("UPDATE documents SET status='parsed' WHERE id=?", (document_id,))

    response = client.get(f"/api/documents/{document_id}/file")
    assert response.status_code == 200

    deleted = client.delete(f"/api/documents/{document_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/documents/{document_id}").status_code == 404
    assert client.get(f"/api/documents/{document_id}/file").status_code == 404
