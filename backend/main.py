import asyncio
import csv
import io
import json
import logging
import os
import re
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import quote
import fitz

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from openpyxl import Workbook
from PIL import Image
from pydantic import BaseModel, Field, field_validator
from jsonschema.exceptions import SchemaError

from .config import public_ai_settings
from . import engine, jobs, master, verify
from .db import FILES, audit, connect, decode, init_db, now
from .parsers import ParseError, parse

logger = logging.getLogger(__name__)

JSON_FIELDS = ("blocks", "result", "groundings", "validation", "parse_options")
PAGE_RANGE_RE = re.compile(r"^\d+(-\d+)?(,\d+(-\d+)?)*$")
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".docx", ".xlsx", ".csv", ".txt", ".md", ".html", ".htm"}
IMAGES = engine.VISION_SUFFIXES - {".pdf"}  # 페이지 이미지를 가진 형식 중 단일 이미지 파일
MAX_UPLOAD = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
# Statuses a stale job may be taken over from, keyed by the status the job claims.
ACTIVE = {"parsing": ("parsing",), "extracting": ("extracting", "validating")}
RUNNING_STATUSES = {"parsing", "extracting", "validating"}  # 실행 중인 잡이 있는 상태(취소는 다음 단계 경계에서)
PROCESSING_STATUSES = {"queued", *RUNNING_STATUSES}  # 삭제 금지·취소 대상 문서 상태


@asynccontextmanager
async def lifespan(_app):
    init_db()
    await asyncio.to_thread(master.ready)  # 첫 요청 전에 마스터 사전 캐시를 미리 채운다(이벤트 루프 밖에서)
    recover()
    yield


app = FastAPI(title="Docraft API", version="0.1.0", lifespan=lifespan)
init_db()  # Also supports test/embedded clients that do not enter ASGI lifespan.
jobs.backend()  # Fail fast on an unknown QUEUE_BACKEND.
origins = [value.strip() for value in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",") if value.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def auth(x_api_key: str | None = Header(None)):
    expected = os.getenv("DOCRAFT_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(401, "유효한 X-API-Key가 필요합니다.")


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class SchemaInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    json_schema: dict


class SchemaPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    json_schema: dict | None = None


class GenerateInput(BaseModel):
    prompt: str = ""
    document_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    name: str = "Generated schema"


class ExtractInput(BaseModel):
    schema_id: str


class BatchExtractInput(BaseModel):
    schema_id: str
    document_ids: list[str] = Field(default_factory=list)


class ReviewInput(BaseModel):
    path: str
    value: object = None


class ParseOptions(BaseModel):
    pages: str | None = None
    provider: Literal["auto", "library", "paddle"] = "auto"
    table_format: Literal["markdown", "html"] = "markdown"

    @field_validator("pages")
    @classmethod
    def _valid_pages(cls, value):
        if value is not None and not PAGE_RANGE_RE.fullmatch(value):
            raise ValueError("페이지 범위 형식이 올바르지 않습니다.")
        return value


def uid(): return uuid.uuid4().hex


def one(db, query, args=(), *, json_fields=()):
    row = db.execute(query, args).fetchone()
    if not row: raise HTTPException(404, "리소스를 찾을 수 없습니다.")
    return decode(row, json_fields)


def document(db, document_id):
    value = one(db, "SELECT * FROM documents WHERE id=?", (document_id,), json_fields=JSON_FIELDS)
    corrections = db.execute("SELECT id,path,old_value,new_value,created_at FROM corrections WHERE document_id=? ORDER BY id", (document_id,)).fetchall()
    value["corrections"] = [{**dict(row), "old_value": json.loads(row["old_value"]) if row["old_value"] else None, "new_value": json.loads(row["new_value"])} for row in corrections]
    value["groundings"] = grounding_list(value["groundings"])
    value.pop("file_path", None)
    value.pop("cancel_requested", None)
    return value


def grounding_list(values, prefix=""):
    items = []
    for name, grounding in values.items():
        path = f"{prefix}.{name}" if prefix else name
        if isinstance(grounding, dict) and "confidence" in grounding:
            item = {**grounding, "path": path, "text": grounding.get("source_text")}
            item.pop("source_text", None)
            items.append(item)
        elif isinstance(grounding, dict):
            items.extend(grounding_list(grounding, path))
    return items


def mark_corrected(values, path):
    parts = path.strip("/").replace("/", ".").split(".")
    target = values
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = {"confidence": 1, "page": None, "bbox": None, "source_text": None, "corrected_by": "human"}


def schema_row(row): return decode(row, ("json_schema",))


@app.get("/api/health")
def health(): return {"status": "ok", "ai": public_ai_settings(), "verify_inflight": INFLIGHT}


@app.get("/api/ai/status", dependencies=[Depends(auth)])
def ai_status(): return public_ai_settings()


@app.get("/api/projects", dependencies=[Depends(auth)])
def list_projects():
    with connect() as db: return [dict(row) for row in db.execute("SELECT * FROM projects ORDER BY created_at DESC")]


@app.post("/api/projects", status_code=201, dependencies=[Depends(auth)])
def create_project(data: ProjectInput):
    project_id, stamp = uid(), now()
    with connect() as db:
        db.execute("INSERT INTO projects VALUES(?,?,?,?,?)", (project_id, data.name, data.description, stamp, stamp))
        audit(db, project_id, "create", "project", project_id)
        return one(db, "SELECT * FROM projects WHERE id=?", (project_id,))


@app.get("/api/projects/{project_id}", dependencies=[Depends(auth)])
def get_project(project_id: str):
    with connect() as db: return one(db, "SELECT * FROM projects WHERE id=?", (project_id,))


@app.patch("/api/projects/{project_id}", dependencies=[Depends(auth)])
def update_project(project_id: str, data: ProjectPatch):
    with connect() as db:
        current = one(db, "SELECT * FROM projects WHERE id=?", (project_id,))
        db.execute("UPDATE projects SET name=?,description=?,updated_at=? WHERE id=?",
                   (data.name if data.name is not None else current["name"],
                    data.description if data.description is not None else current["description"], now(), project_id))
        audit(db, project_id, "update", "project", project_id)
        return one(db, "SELECT * FROM projects WHERE id=?", (project_id,))


@app.delete("/api/projects/{project_id}", status_code=204, dependencies=[Depends(auth)])
def delete_project(project_id: str):
    with connect() as db:
        one(db, "SELECT id FROM projects WHERE id=?", (project_id,))
        audit(db, project_id, "delete", "project", project_id)
        paths = [row["file_path"] for row in db.execute("SELECT file_path FROM documents WHERE project_id=?", (project_id,)).fetchall()]
        db.execute("DELETE FROM documents WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM schemas WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))
    for path in paths: remove_file(path)


DOCUMENT_LIST_COLUMNS = "id,project_id,filename,media_type,size,status,error,schema_id,approved_at,created_at,updated_at,result,validation"


@app.get("/api/projects/{project_id}/documents", dependencies=[Depends(auth)])
def list_documents(project_id: str):
    with connect() as db:
        one(db, "SELECT id FROM projects WHERE id=?", (project_id,))
        rows = db.execute(f"SELECT {DOCUMENT_LIST_COLUMNS} FROM documents WHERE project_id=? ORDER BY created_at DESC", (project_id,)).fetchall()
        return [decode(row, ("result", "validation")) for row in rows]


async def save_upload(upload: UploadFile, target: Path):
    size = 0
    with target.open("wb") as out:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD:
                out.close(); target.unlink(missing_ok=True)
                raise HTTPException(413, f"파일 크기는 {MAX_UPLOAD} 바이트 이하여야 합니다.")
            out.write(chunk)
    return size


@app.post("/api/projects/{project_id}/documents", status_code=202, dependencies=[Depends(auth)])
async def upload_documents(project_id: str, files: list[UploadFile] = File(...)):
    created, staged = [], []
    with connect() as db:
        one(db, "SELECT id FROM projects WHERE id=?", (project_id,))
    for upload in files:
        suffix = Path(Path(upload.filename or "upload").name).suffix.lower()
        if suffix not in ALLOWED: raise HTTPException(415, f"지원하지 않는 파일 형식입니다: {suffix}")
    try:
        for upload in files:
            filename = Path(upload.filename or "upload").name
            suffix = Path(filename).suffix.lower()
            document_id, stamp = uid(), now()
            target = FILES / f"{document_id}{suffix}"
            size = await save_upload(upload, target)
            staged.append((document_id, filename, upload.content_type or "application/octet-stream", size, target, stamp))
    except Exception:
        for *_, target, _stamp in staged: target.unlink(missing_ok=True)
        raise
    with connect() as db:
        for document_id, filename, media_type, size, target, stamp in staged:
            db.execute("INSERT INTO documents(id,project_id,filename,media_type,size,file_path,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (document_id, project_id, filename, media_type, size, str(target), "queued", stamp, stamp))
            audit(db, project_id, "upload", "document", document_id, {"filename": filename, "size": size})
            logger.info("upload saved: document=%s filename=%s size=%d", document_id, filename, size)
            created.append(document(db, document_id))
    for item in created: dispatch(item["id"], "parse")  # After commit, so workers see the queued row.
    return created


@app.get("/api/documents/{document_id}", dependencies=[Depends(auth)])
def get_document(document_id: str):
    with connect() as db: return document(db, document_id)


def remove_file(file_path):
    """Delete an uploaded original; only files under FILES, so a tampered path never reaches elsewhere."""
    path = Path(file_path).resolve()
    if path.parent == FILES.resolve(): path.unlink(missing_ok=True)


@app.delete("/api/documents/{document_id}", status_code=204, dependencies=[Depends(auth)])
def delete_document(document_id: str):
    with connect() as db:
        doc = one(db, "SELECT * FROM documents WHERE id=?", (document_id,))
        if doc["status"] in PROCESSING_STATUSES:
            raise HTTPException(409, "처리 중인 문서는 삭제할 수 없습니다.")
        audit(db, doc["project_id"], "delete", "document", document_id, {"filename": doc["filename"]})
        db.execute("DELETE FROM documents WHERE id=?", (document_id,))
        remove_file(doc["file_path"])


def stale_before():
    return (datetime.now(timezone.utc) - timedelta(seconds=jobs.LEASE)).isoformat()


def claim(db, document_id, status):
    """Move a queued document, or one whose job stopped heartbeating, to `status`; False when a live job owns it (or it is gone)."""
    active = ACTIVE[status]
    claimed = db.execute(
        f"UPDATE documents SET status=?,error=NULL,updated_at=? WHERE id=? AND (status='queued' OR (status IN ({','.join('?' * len(active))}) AND updated_at<?))",
        (status, now(), document_id, *active, stale_before()),
    ).rowcount
    if not claimed: logger.warning("job skipped, document not queued: document=%s target=%s", document_id, status)
    return bool(claimed)


TASK_IDS: dict[str, str] = {}  # document_id -> Celery task id(있으면). API 프로세스만 큐에 넣으므로 이 메모리만으로 충분하다.


def dispatch(document_id, name, *args):
    """작업을 큐에 넣고, Celery면 나중에 cancel이 revoke할 수 있도록 task id를 기억해둔다."""
    result = jobs.enqueue(name, document_id, *args)
    task_id = getattr(result, "id", None)
    if task_id: TASK_IDS[document_id] = task_id


def check_cancel(db, document_id):
    """운영자가 이 문서의 취소를 요청했으면(``cancel_requested``) status를 canceled로 남기고 True를 돌려준다.

    parse·extract 잡의 단계 경계(파싱 뒤, 추출 뒤, 검증 뒤)에서만 확인한다 — verify._check와 같은
    협조적 취소이며, 진행 중인 단일 호출(파싱·추출 자체)을 중간에 끊지는 않는다.
    """
    row = one(db, "SELECT cancel_requested FROM documents WHERE id=?", (document_id,))
    if not row["cancel_requested"]: return False
    db.execute("UPDATE documents SET status='canceled',cancel_requested=FALSE,updated_at=? WHERE id=?", (now(), document_id))
    return True


@contextmanager
def heartbeat(document_id):
    """Refresh updated_at while a job runs so claim() only takes over jobs whose worker died."""
    stop = threading.Event()
    def beat():
        while not stop.wait(jobs.LEASE / 3):
            with connect() as db: db.execute("UPDATE documents SET updated_at=? WHERE id=? AND status IN ('parsing','extracting','validating')", (now(), document_id))
    threading.Thread(target=beat, daemon=True).start()
    try: yield
    finally: stop.set()


def recover():
    """Re-enqueue queued documents and jobs whose worker died; lost inline jobs and dropped broker messages resume on API start."""
    with connect() as db:
        rows = db.execute("SELECT id,schema_id,markdown IS NOT NULL AS parsed FROM documents WHERE status='queued' OR (status IN ('parsing','extracting','validating') AND updated_at<?)", (stale_before(),)).fetchall()
    for row in rows:
        if row["parsed"]: dispatch(row["id"], "extract", row["schema_id"])
        else: dispatch(row["id"], "parse")
    if rows: logger.info("recovered jobs: %d", len(rows))


@jobs.task("parse")
def run_parse(document_id: str):
    with connect() as db:
        if not claim(db, document_id, "parsing"): return
        row = one(db, "SELECT * FROM documents WHERE id=?", (document_id,), json_fields=("parse_options",))
    logger.info("parse start: document=%s filename=%s", document_id, row["filename"])
    started = time.monotonic()
    try:
        with heartbeat(document_id): markdown, blocks = parse(row["file_path"], row["filename"], row["media_type"], row["parse_options"])
        with connect() as db:
            if check_cancel(db, document_id):
                logger.info("status transition: document=%s status=canceled (parse)", document_id)
                return
            db.execute("UPDATE documents SET status='parsed',markdown=?,blocks=?,updated_at=? WHERE id=?", (markdown, json.dumps(blocks, ensure_ascii=False), now(), document_id))
            audit(db, row["project_id"], "parse", "document", document_id, {"blocks": len(blocks)})
        logger.info("parse finished: document=%s blocks=%d elapsed=%.2fs", document_id, len(blocks), time.monotonic() - started)
    except Exception as exc:
        message = str(exc) if isinstance(exc, ParseError) else f"문서 파싱 실패: {exc}"
        logger.exception("parse failed: document=%s elapsed=%.2fs", document_id, time.monotonic() - started)
        with connect() as db: db.execute("UPDATE documents SET status='failed',error=?,updated_at=? WHERE id=?", (message, now(), document_id))


@app.post("/api/documents/{document_id}/parse", status_code=202, dependencies=[Depends(auth)])
def retry_parse(document_id: str, data: ParseOptions | None = None):
    with connect() as db:
        current = one(db, "SELECT parse_options FROM documents WHERE id=?", (document_id,), json_fields=("parse_options",))
        options = data.model_dump() if data is not None else current["parse_options"]
        db.execute("UPDATE documents SET status='queued',error=NULL,markdown=NULL,blocks='[]',result=NULL,groundings='{}',validation='[]',schema_id=NULL,approved_at=NULL,parse_options=?,updated_at=? WHERE id=?", (json.dumps(options, ensure_ascii=False), now(), document_id))
    dispatch(document_id, "parse")
    return {"id": document_id, "status": "queued"}


@app.post("/api/documents/{document_id}/cancel", dependencies=[Depends(auth)])
def cancel_document(document_id: str):
    """대기 중인 문서는 바로 canceled로 옮기고, 처리 중인 문서는 다음 단계 경계에서 스스로 멈추도록 표시한다.

    이미 끝났거나 취소된 문서(파싱 완료·검토 필요·완료·실패·취소됨)는 취소할 잡이 없어 409다.
    """
    with connect() as db:
        doc = one(db, "SELECT status,project_id FROM documents WHERE id=?", (document_id,))
        if doc["status"] == "queued":
            db.execute("UPDATE documents SET status='canceled',updated_at=? WHERE id=?", (now(), document_id))
        elif doc["status"] in RUNNING_STATUSES:
            db.execute("UPDATE documents SET cancel_requested=TRUE,updated_at=? WHERE id=?", (now(), document_id))
        else:
            raise HTTPException(409, "대기 중이거나 처리 중인 문서만 취소할 수 있습니다.")
        jobs.revoke(TASK_IDS.pop(document_id, None))
        audit(db, doc["project_id"], "cancel", "document", document_id)
        logger.info("status transition: document=%s cancel requested (was %s)", document_id, doc["status"])
        return document(db, document_id)


@app.get("/api/projects/{project_id}/schemas", dependencies=[Depends(auth)])
def list_schemas(project_id: str):
    with connect() as db:
        one(db, "SELECT id FROM projects WHERE id=?", (project_id,))
        return [schema_row(row) for row in db.execute("SELECT * FROM schemas WHERE project_id=? ORDER BY name,version DESC", (project_id,))]


def persist_schema(db, project_id, name, definition):
    engine.Draft202012Validator.check_schema(definition)
    version = db.execute("SELECT COALESCE(MAX(version),0)+1 AS version FROM schemas WHERE project_id=? AND name=?", (project_id, name)).fetchone()["version"]
    schema_id, stamp = uid(), now()
    db.execute("INSERT INTO schemas VALUES(?,?,?,?,?,?)", (schema_id, project_id, name, version, json.dumps(definition, ensure_ascii=False), stamp))
    audit(db, project_id, "create", "schema", schema_id, {"version": version})
    return schema_row(db.execute("SELECT * FROM schemas WHERE id=?", (schema_id,)).fetchone())


@app.post("/api/projects/{project_id}/schemas", status_code=201, dependencies=[Depends(auth)])
def create_schema(project_id: str, data: SchemaInput):
    with connect() as db:
        one(db, "SELECT id FROM projects WHERE id=?", (project_id,))
        try: return persist_schema(db, project_id, data.name, data.json_schema)
        except SchemaError as exc: raise HTTPException(422, f"유효하지 않은 JSON Schema: {exc.message}")


@app.get("/api/schemas/{schema_id}", dependencies=[Depends(auth)])
def get_schema(schema_id: str):
    with connect() as db: return schema_row(one(db, "SELECT * FROM schemas WHERE id=?", (schema_id,)))


@app.patch("/api/schemas/{schema_id}", status_code=201, dependencies=[Depends(auth)])
def update_schema(schema_id: str, data: SchemaPatch):
    with connect() as db:
        current = schema_row(one(db, "SELECT * FROM schemas WHERE id=?", (schema_id,)))
        name = data.name if data.name is not None else current["name"]
        definition = data.json_schema if data.json_schema is not None else current["json_schema"]
        try: return persist_schema(db, current["project_id"], name, definition)
        except SchemaError as exc: raise HTTPException(422, f"유효하지 않은 JSON Schema: {exc.message}")


@app.delete("/api/schemas/{schema_id}", status_code=204, dependencies=[Depends(auth)])
def delete_schema(schema_id: str):
    with connect() as db:
        schema = one(db, "SELECT * FROM schemas WHERE id=?", (schema_id,))
        used = db.execute("SELECT id FROM documents WHERE schema_id=? LIMIT 1", (schema_id,)).fetchone()
        if used: raise HTTPException(409, "이 스키마 버전을 사용한 문서가 있어 삭제할 수 없습니다.")
        db.execute("DELETE FROM schemas WHERE id=?", (schema_id,))
        audit(db, schema["project_id"], "delete", "schema", schema_id)


@app.post("/api/projects/{project_id}/schemas/generate", status_code=201, dependencies=[Depends(auth)])
def generate(project_id: str, data: GenerateInput):
    references = list(dict.fromkeys(([data.document_id] if data.document_id else []) + data.document_ids))
    if not references:
        raise HTTPException(422, "스키마 자동 생성에는 파싱 완료된 참조 문서가 필요합니다.")
    with connect() as db:
        one(db, "SELECT id FROM projects WHERE id=?", (project_id,))
        docs = []
        for document_id in references:
            doc = one(db, "SELECT * FROM documents WHERE id=?", (document_id,))
            if doc["project_id"] != project_id: raise HTTPException(409, "문서가 이 프로젝트에 속하지 않습니다.")
            if doc["status"] not in {"parsed", "needs_review", "completed"} or not (doc["markdown"] or "").strip():
                raise HTTPException(409, "OCR/파싱 완료 후 스키마를 자동 생성할 수 있습니다.")
            docs.append(doc)
        logger.info("schema generation start: project=%s docs=%d", project_id, len(docs))
        try: definition = engine.generate_schema_from_documents(data.prompt, docs)
        except Exception as exc:
            logger.exception("schema generation failed: project=%s", project_id)
            raise HTTPException(502, f"AI 스키마 생성 실패: {exc}")
        try:
            created = persist_schema(db, project_id, data.name, definition)
        except SchemaError as exc: raise HTTPException(502, f"AI가 유효하지 않은 JSON Schema를 반환했습니다: {exc.message}")
        logger.info("schema generation finished: project=%s schema=%s", project_id, created["id"])
        return created


@jobs.task("extract")
def run_extract(document_id, schema_id):
    with connect() as db:
        if not claim(db, document_id, "extracting"): return
        doc = one(db, "SELECT * FROM documents WHERE id=?", (document_id,), json_fields=("blocks",))
        schema = schema_row(db.execute("SELECT * FROM schemas WHERE id=?", (schema_id,)).fetchone())
    logger.info("extract start: document=%s schema=%s", document_id, schema_id)
    started = time.monotonic()
    try:
        with heartbeat(document_id): result, groundings = engine.extract(schema["json_schema"], doc["blocks"], doc["file_path"])
        with connect() as db:
            if check_cancel(db, document_id):
                logger.info("status transition: document=%s status=canceled (extract)", document_id)
                return
            db.execute("UPDATE documents SET status='validating',result=?,groundings=?,updated_at=? WHERE id=?", (json.dumps(result, ensure_ascii=False), json.dumps(groundings, ensure_ascii=False), now(), document_id))
        issues = engine.validate(result, schema["json_schema"], groundings)
        status = "needs_review" if issues else "completed"
        with connect() as db:
            if check_cancel(db, document_id):
                logger.info("status transition: document=%s status=canceled (validate)", document_id)
                return
            db.execute("UPDATE documents SET status=?,validation=?,updated_at=? WHERE id=?", (status, json.dumps(issues, ensure_ascii=False), now(), document_id))
            audit(db, doc["project_id"], "extract", "document", document_id, {"schema_id": schema_id, "issues": len(issues)})
        logger.info("extract finished: document=%s status=%s issues=%d elapsed=%.2fs", document_id, status, len(issues), time.monotonic() - started)
    except Exception as exc:
        logger.exception("extract failed: document=%s elapsed=%.2fs", document_id, time.monotonic() - started)
        with connect() as db: db.execute("UPDATE documents SET status='failed',error=?,updated_at=? WHERE id=?", (f"추출 실패: {exc}", now(), document_id))


EXTRACTABLE_STATUSES = {"parsed", "needs_review", "completed"}


def extract_reason(doc, project_id, mismatch):
    """None when `doc` (a row with project_id/status/filename, or None) may be queued, else a Korean skip reason."""
    if doc is None: return "문서를 찾을 수 없습니다."
    if doc["project_id"] != project_id: return mismatch
    if doc["status"] not in EXTRACTABLE_STATUSES: return "파싱 완료 후 추출할 수 있습니다."
    return None


def mark_queued(db, document_id, schema_id):
    """Queue an extract; schema_id is stored now so recover() can re-enqueue it."""
    db.execute("UPDATE documents SET status='queued',error=NULL,schema_id=?,updated_at=? WHERE id=?", (schema_id, now(), document_id))


@app.post("/api/documents/{document_id}/extract", status_code=202, dependencies=[Depends(auth)])
def start_extract(document_id: str, data: ExtractInput):
    with connect() as db:
        doc = one(db, "SELECT project_id,status FROM documents WHERE id=?", (document_id,))
        schema = one(db, "SELECT project_id FROM schemas WHERE id=?", (data.schema_id,))
        reason = extract_reason(doc, schema["project_id"], "문서와 스키마의 프로젝트가 다릅니다.")
        if reason: raise HTTPException(409, reason)
        mark_queued(db, document_id, data.schema_id)
    dispatch(document_id, "extract", data.schema_id)
    return {"id": document_id, "status": "queued"}


@app.post("/api/projects/{project_id}/extract", status_code=202, dependencies=[Depends(auth)])
def batch_extract(project_id: str, data: BatchExtractInput):
    with connect() as db:
        one(db, "SELECT id FROM projects WHERE id=?", (project_id,))
        schema = one(db, "SELECT project_id FROM schemas WHERE id=?", (data.schema_id,))
        if schema["project_id"] != project_id: raise HTTPException(409, "스키마가 이 프로젝트에 속하지 않습니다.")
        if data.document_ids:
            targets = [(doc_id, db.execute("SELECT project_id,status,filename FROM documents WHERE id=?", (doc_id,)).fetchone()) for doc_id in data.document_ids]
        else:
            rows = db.execute("SELECT id,project_id,status,filename FROM documents WHERE project_id=? ORDER BY created_at", (project_id,)).fetchall()
            targets = [(row["id"], row) for row in rows]
        queued, skipped = [], []
        for doc_id, doc in targets:
            reason = extract_reason(doc, project_id, "다른 프로젝트의 문서입니다.")
            if reason:
                skipped.append({"id": doc_id, "filename": doc["filename"] if doc else None, "reason": reason})
                continue
            mark_queued(db, doc_id, data.schema_id)
            queued.append(doc_id)
    for doc_id in queued: dispatch(doc_id, "extract", data.schema_id)
    return {"queued": queued, "skipped": skipped}


def _schema_for_document(db, doc):
    if not doc.get("schema_id"): raise HTTPException(409, "추출 결과가 없습니다.")
    return schema_row(db.execute("SELECT * FROM schemas WHERE id=?", (doc["schema_id"],)).fetchone())


@app.patch("/api/documents/{document_id}/review", dependencies=[Depends(auth)])
def review(document_id: str, data: ReviewInput):
    with connect() as db:
        doc = one(db, "SELECT * FROM documents WHERE id=?", (document_id,), json_fields=("result", "groundings"))
        if doc["result"] is None: raise HTTPException(409, "수정할 추출 결과가 없습니다.")
        schema = _schema_for_document(db, doc)
        try: result, old = engine.set_pointer(doc["result"], data.path, data.value)
        except (KeyError, IndexError, ValueError, TypeError) as exc: raise HTTPException(422, f"수정 경로가 유효하지 않습니다: {exc}")
        groundings = doc["groundings"]
        mark_corrected(groundings, data.path)
        issues = engine.validate(result, schema["json_schema"], groundings)
        stamp = now()
        db.execute("UPDATE documents SET result=?,groundings=?,validation=?,status='needs_review',approved_at=NULL,updated_at=? WHERE id=?", (json.dumps(result, ensure_ascii=False), json.dumps(groundings, ensure_ascii=False), json.dumps(issues, ensure_ascii=False), stamp, document_id))
        db.execute("INSERT INTO corrections(document_id,path,old_value,new_value,created_at) VALUES(?,?,?,?,?)", (document_id, data.path, json.dumps(old, ensure_ascii=False), json.dumps(data.value, ensure_ascii=False), stamp))
        audit(db, doc["project_id"], "correct", "document", document_id, {"path": data.path})
        logger.info("status transition: document=%s status=needs_review (correction path=%s)", document_id, data.path)
        return document(db, document_id)


@app.post("/api/documents/{document_id}/approve", dependencies=[Depends(auth)])
def approve(document_id: str):
    with connect() as db:
        doc = one(db, "SELECT * FROM documents WHERE id=?", (document_id,), json_fields=("result", "groundings"))
        if doc["result"] is None: raise HTTPException(409, "승인할 추출 결과가 없습니다.")
        schema = _schema_for_document(db, doc)
        issues = [issue for issue in engine.validate(doc["result"], schema["json_schema"], doc["groundings"]) if issue["code"] != "low_confidence"]
        if issues: raise HTTPException(422, {"message": "검증 오류를 수정한 후 승인할 수 있습니다.", "validation": issues})
        stamp = now()
        db.execute("UPDATE documents SET status='completed',validation='[]',approved_at=?,updated_at=? WHERE id=?", (stamp, stamp, document_id))
        audit(db, doc["project_id"], "approve", "document", document_id)
        logger.info("status transition: document=%s status=completed", document_id)
        return document(db, document_id)


def dotted(value, prefix, out):
    """Flatten scalars/dicts to dotted keys in `out`; any list becomes one JSON-string cell."""
    if isinstance(value, dict):
        for key, child in value.items(): dotted(child, f"{prefix}.{key}" if prefix else key, out)
    elif isinstance(value, list): out[prefix] = json.dumps(value, ensure_ascii=False)
    else: out[prefix] = value
    return out


def table_rows(result):
    """Row-major view of an extraction result: object-lists expand into rows (item i -> row i), everything else repeats on every row."""
    scalars, lists = {}, {}
    for key, value in (result.items() if isinstance(result, dict) else {"": result}.items()):
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            lists[key] = [dotted(item, key, {}) for item in value]
        else:
            dotted(value, key, scalars)
    row_count = max(1, max((len(items) for items in lists.values()), default=0))
    rows = []
    for i in range(row_count):
        row = dict(scalars)
        for items in lists.values():
            if i < len(items): row.update(items[i])
        rows.append(row)
    return rows


def content_disposition(stem, ext):
    filename = f"{stem}.{ext}"
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or f"export.{ext}"
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"}


def safe_stem(name, fallback):
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", name).strip()
    return cleaned or fallback


def table_response(rows, stem, format, columns=None):
    if format not in ("csv", "xlsx"): raise HTTPException(422, "format은 json, csv, xlsx 중 하나여야 합니다.")
    columns = columns or list(dict.fromkeys(key for row in rows for key in row))
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, restval="")
        writer.writeheader(); writer.writerows(rows)
        return Response(output.getvalue(), media_type="text/csv; charset=utf-8", headers=content_disposition(stem, "csv"))
    workbook = Workbook(); sheet = workbook.active; sheet.title = "result"
    sheet.append(columns)
    for row in rows: sheet.append([row.get(column, "") for column in columns])
    buffer = io.BytesIO(); workbook.save(buffer)
    return Response(buffer.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=content_disposition(stem, "xlsx"))


@app.get("/api/documents/{document_id}/export", dependencies=[Depends(auth)])
def export(document_id: str, format: str = "json"):
    with connect() as db: doc = one(db, "SELECT filename,result FROM documents WHERE id=?", (document_id,), json_fields=("result",))
    if doc["result"] is None: raise HTTPException(409, "내보낼 추출 결과가 없습니다.")
    stem = Path(doc["filename"]).stem
    if format == "json":
        return Response(json.dumps(doc["result"], ensure_ascii=False, indent=2), media_type="application/json", headers=content_disposition(stem, "json"))
    return table_response(table_rows(doc["result"]), stem, format)


@app.get("/api/projects/{project_id}/export", dependencies=[Depends(auth)])
def export_project(project_id: str, format: str = "json", schema_id: str | None = None):
    with connect() as db:
        proj = one(db, "SELECT * FROM projects WHERE id=?", (project_id,))
        query, args = "SELECT id,filename,status,schema_id,result FROM documents WHERE project_id=? AND result IS NOT NULL", [project_id]
        if schema_id: query, args = query + " AND schema_id=?", args + [schema_id]
        docs = [decode(row, ("result",)) for row in db.execute(query + " ORDER BY created_at", tuple(args)).fetchall()]
    stem = safe_stem(proj["name"], f"docraft-{project_id}")
    if format == "json":
        payload = [{"document_id": doc["id"], "filename": doc["filename"], "status": doc["status"], "schema_id": doc["schema_id"], "result": doc["result"]} for doc in docs]
        return Response(json.dumps(payload, ensure_ascii=False, indent=2), media_type="application/json", headers=content_disposition(stem, "json"))
    rows = [{"document_id": doc["id"], "filename": doc["filename"], "status": doc["status"], **row} for doc in docs for row in table_rows(doc["result"])]
    return table_response(rows, stem, format, columns=["document_id", "filename", "status"] if not rows else None)


@app.get("/api/documents/{document_id}/file", dependencies=[Depends(auth)])
def original_file(document_id: str):
    with connect() as db: doc = one(db, "SELECT filename,media_type,file_path FROM documents WHERE id=?", (document_id,))
    path = Path(doc["file_path"]).resolve()
    if path.parent != FILES.resolve() or not path.is_file(): raise HTTPException(404, "원본 파일을 찾을 수 없습니다.")
    return FileResponse(path, media_type=doc["media_type"], filename=doc["filename"])


@app.get("/api/documents/{document_id}/pages", dependencies=[Depends(auth)])
def document_pages(document_id: str):
    with connect() as db: doc = one(db, "SELECT filename,file_path FROM documents WHERE id=?", (document_id,))
    path = Path(doc["file_path"]).resolve()
    if path.parent != FILES.resolve() or not path.is_file(): raise HTTPException(404, "원본 파일을 찾을 수 없습니다.")
    if path.suffix.lower() != ".pdf": raise HTTPException(415, "PDF 문서만 페이지 목록을 제공합니다.")
    with fitz.open(path) as pdf:
        return [{"page": index + 1, "width": page.rect.width, "height": page.rect.height} for index, page in enumerate(pdf)]


@app.get("/api/documents/{document_id}/pages/{page}/preview", dependencies=[Depends(auth)])
def document_page_preview(document_id: str, page: int):
    with connect() as db: doc = one(db, "SELECT filename,file_path FROM documents WHERE id=?", (document_id,))
    path = Path(doc["file_path"]).resolve()
    if path.parent != FILES.resolve() or not path.is_file(): raise HTTPException(404, "원본 파일을 찾을 수 없습니다.")
    if path.suffix.lower() != ".pdf": raise HTTPException(415, "PDF 문서만 페이지 미리보기를 제공합니다.")
    with fitz.open(path) as pdf:
        if not 1 <= page <= len(pdf): raise HTTPException(404, "페이지를 찾을 수 없습니다.")
        pixmap = pdf[page - 1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        return Response(pixmap.tobytes("png"), media_type="image/png")


def frames(path):
    """이미지 파일의 프레임 수. 다중 페이지 TIF를 가려내는 데 쓴다."""
    try:
        with Image.open(path) as image: return getattr(image, "n_frames", 1)
    except Exception: return 1


INFLIGHT = 0  # 처리 중인 /api/verify·/api/read 수(합계). health의 verify_inflight로 노출해 배포 스크립트가 교체를 미룬다
INFLIGHT_EVENTS: set[threading.Event] = set()  # 진행 중인 호출마다 하나씩, cancel-all이 한꺼번에 세운다
_inflight_lock = threading.Lock()


def cancelled_response(exc, action, doc_type):
    """``verify.Cancelled``를 라우트 응답으로 바꾼다. 운영자의 cancel-all이 세운 것(reason="operator")이면
    409(진행 중 판단으로 오인하지 않게 클라이언트 연결 끊김의 499와 구분), 아니면 499다."""
    if exc.args and exc.args[0] == "operator":
        logger.info("%s: cancelled by operator doc_type=%s", action, doc_type)
        raise HTTPException(409, "운영자에 의해 작업이 취소되었습니다.")
    logger.info("%s: cancelled (client disconnected) doc_type=%s", action, doc_type)
    return Response(status_code=499)


async def process_image(request: Request, image: UploadFile, fn, *args):
    """단일 페이지 이미지 업로드를 저장하고 ``fn(경로, *args, cancel=cancel)``을 이벤트 루프 밖 스레드에서 돌린다.

    /api/verify·/api/read가 함께 쓰는 업로드·임시파일·다중 페이지 검사·취소·in-flight 계수 처리다.
    파싱·추출·Judge로 수 분 걸리므로 스레드에서 돌린다 — 안 그러면 health까지 막혀 동시 요청이 줄을 선다.
    클라이언트가 끊기면 다음 단계(추출·Judge) 전에 ``cancel``을 세워 ``fn``이 ``verify.Cancelled``로 멈추게 한다.
    ``(fn의 결과, 저장 파일명, 시작 시각(monotonic))``을 돌려준다.
    """
    filename = Path(image.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in IMAGES: raise HTTPException(415, f"이미지 파일만 지원합니다: {suffix or image.content_type}")
    started = time.monotonic()
    global INFLIGHT
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / f"{uid()}{suffix}"
        await save_upload(image, target)
        if frames(target) > 1: raise HTTPException(422, "다중 페이지 문서는 아직 지원하지 않습니다.")
        INFLIGHT += 1
        cancel = threading.Event()
        with _inflight_lock: INFLIGHT_EVENTS.add(cancel)
        try:
            task = asyncio.ensure_future(asyncio.to_thread(fn, str(target), *args, cancel=cancel))
            while not task.done():
                if await request.is_disconnected(): cancel.set()
                await asyncio.wait({task}, timeout=1)
            return task.result(), filename, started
        finally:
            INFLIGHT -= 1
            with _inflight_lock: INFLIGHT_EVENTS.discard(cancel)


@app.post("/api/verify", dependencies=[Depends(auth)])
async def verify_result(request: Request, image: UploadFile = File(...), ao_result: str = Form(...), doc_type: str | None = Form(None),
                        hint_paths: str | None = Form(None)):
    """AO 결과 JSON(API·UI 형식)과 원본 이미지를 받아 필드별로 교차검증·교정한 JSON을 돌려준다.

    ``hint_paths``(JSON 배열 문자열, 예: ``["병원명", "항목내역"]``)를 주면 그 key만 비교·판정하고
    나머지는 AO 값 그대로 돌려준다(판정 정보 없음). 자세한 규칙은 ``verify.run`` 참고.
    """
    try:
        ao = json.loads(ao_result)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "ao_result를 JSON으로 해석할 수 없습니다.") from exc
    try:
        verify.document(ao)
    except (AttributeError, ValueError) as exc:
        raise HTTPException(422, "ao_result에 documents(또는 result)가 없습니다.") from exc
    hints = None
    if hint_paths:
        try:
            hints = json.loads(hint_paths)
        except json.JSONDecodeError as exc:
            raise HTTPException(422, "hint_paths를 JSON으로 해석할 수 없습니다.") from exc
        if not isinstance(hints, list) or not all(isinstance(key, str) for key in hints):
            raise HTTPException(422, "hint_paths는 문자열 배열이어야 합니다.")
    try:
        result, filename, started = await process_image(request, image, verify.run, ao, doc_type, hints)
    except verify.Cancelled as exc:
        return cancelled_response(exc, "verify", doc_type)
    except HTTPException:  # process_image가 낸 415·413·422(다중 페이지)는 그대로 올린다
        raise
    except ValueError as exc:  # ParseError 포함
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logger.exception("verify failed: doc_type=%s", doc_type)
        raise HTTPException(502, f"교차검증에 실패했습니다: {exc}") from exc
    logger.info("verify finished: filename=%s counts=%s elapsed=%.2fs", filename, verify.document(result)["verify"]["counts"], time.monotonic() - started)
    return result


@app.post("/api/read", dependencies=[Depends(auth)])
async def read_document(request: Request, image: UploadFile = File(...), doc_type: str = Form(...), keys: str | None = Form(None)):
    """이미지에서 Docraft 자체 추출 결과만 돌려준다 — AO 비교·교정·Judge는 하지 않는다. 하네스의 재읽기,
    크롭 재추출(자기 교정), 폴백에 쓰는 순수 읽기 경로다.

    ``keys``(JSON 배열 문자열, 예: ``["병원명", "항목내역"]``)를 주면 그 필드·표 key만 추출한다(추출 스키마도
    그만큼 좁힌다). 정의에 없는 key는 무시하고 한 번 경고 로그를 남기며, 유효한 key가 하나도 없으면 422.
    생략하면 유형의 전체 필드를 돌려준다.
    """
    try:
        doc_type = verify.resolve_doc_type(doc_type)
        wanted = json.loads(keys) if keys else None
        if keys and (not isinstance(wanted, list) or not all(isinstance(key, str) for key in wanted)):
            raise ValueError("keys는 문자열 배열이어야 합니다.")
        only = verify.resolve_keys(doc_type, wanted, label="keys")
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "keys를 JSON으로 해석할 수 없습니다.") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    def run_read(path, cancel=None):
        return verify.read(path, doc_type, only, cancel=cancel)[1]

    try:
        fields, filename, started = await process_image(request, image, run_read)
    except verify.Cancelled as exc:
        return cancelled_response(exc, "read", doc_type)
    except HTTPException:  # process_image가 낸 415·413·422(다중 페이지)는 그대로 올린다
        raise
    except ValueError as exc:  # ParseError 포함
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logger.exception("read failed: doc_type=%s", doc_type)
        raise HTTPException(502, f"읽기에 실패했습니다: {exc}") from exc
    if only is not None:
        fields = {key: value for key, value in fields.items() if key in only}
    elapsed_ms = round((time.monotonic() - started) * 1000)
    logger.info("read finished: filename=%s doc_type=%s fields=%d elapsed_ms=%d", filename, doc_type, len(fields), elapsed_ms)
    return {"doc_type": doc_type, "fields": fields, "elapsed_ms": elapsed_ms}


@app.post("/api/admin/cancel-all", dependencies=[Depends(auth)])
def cancel_all(confirm: bool = False):
    """운영자 긴급 중지: 대기·처리 중인 문서 잡을 모두 취소하고, 진행 중인 모든 /api/verify·/api/read 호출을
    끊는다(409 "운영자에 의해 작업이 취소되었습니다" — 클라이언트 연결 끊김의 499와 구분된다).

    되돌릴 수 없으므로 ``confirm=true``가 없으면 422다.
    """
    if not confirm: raise HTTPException(422, "confirm=true가 필요합니다.")
    stamp = now()
    with connect() as db:
        queued = db.execute("UPDATE documents SET status='canceled',updated_at=? WHERE status='queued' RETURNING id,project_id", (stamp,)).fetchall()
        running = db.execute(
            f"UPDATE documents SET cancel_requested=TRUE,updated_at=? WHERE status IN ({','.join('?' * len(RUNNING_STATUSES))}) RETURNING id,project_id",
            (stamp, *RUNNING_STATUSES),
        ).fetchall()
        for row in (*queued, *running):
            jobs.revoke(TASK_IDS.pop(row["id"], None))
            audit(db, row["project_id"], "cancel", "document", row["id"])
    with _inflight_lock: events = list(INFLIGHT_EVENTS)
    for event in events:
        event.reason = "operator"
        event.set()
    logger.warning("admin cancel-all: queued=%d running=%d inflight=%d", len(queued), len(running), len(events))
    return {"queued_canceled": len(queued), "running_canceled": len(running), "inflight_canceled": len(events)}
