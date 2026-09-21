"""PostgreSQL integration coverage for the project workspace API."""

import io
import time

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
    monkeypatch.setattr("backend.main.engine.extract", lambda _schema, _blocks: ({"name": "fixture"}, {"name": {"confidence": 1, "page": None, "bbox": None, "source_text": "name: fixture"}}))
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
