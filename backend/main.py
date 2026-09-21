import csv
import io
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
import fitz

from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from jsonschema.exceptions import SchemaError

from .config import public_ai_settings
from . import engine
from .db import FILES, audit, connect, decode, init_db, now
from .parsers import ParseError, parse

logger = logging.getLogger(__name__)

JSON_FIELDS = ("blocks", "result", "groundings", "validation")
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".docx", ".xlsx", ".csv", ".txt", ".md"}
MAX_UPLOAD = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="Docraft API", version="0.1.0", lifespan=lifespan)
init_db()  # Also supports test/embedded clients that do not enter ASGI lifespan.
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


class ReviewInput(BaseModel):
    path: str
    value: object = None


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
def health(): return {"status": "ok", "ai": public_ai_settings()}


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
        db.execute("DELETE FROM documents WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM schemas WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))


@app.get("/api/projects/{project_id}/documents", dependencies=[Depends(auth)])
def list_documents(project_id: str):
    with connect() as db:
        one(db, "SELECT id FROM projects WHERE id=?", (project_id,))
        return [document(db, row["id"]) for row in db.execute("SELECT id FROM documents WHERE project_id=? ORDER BY created_at DESC", (project_id,))]


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
async def upload_documents(project_id: str, background: BackgroundTasks, files: list[UploadFile] = File(...)):
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
            background.add_task(run_parse, document_id)
    return created


@app.get("/api/documents/{document_id}", dependencies=[Depends(auth)])
def get_document(document_id: str):
    with connect() as db: return document(db, document_id)


def run_parse(document_id: str):
    with connect() as db:
        row = one(db, "SELECT * FROM documents WHERE id=?", (document_id,))
        db.execute("UPDATE documents SET status='parsing',error=NULL,updated_at=? WHERE id=?", (now(), document_id))
    logger.info("parse start: document=%s filename=%s", document_id, row["filename"])
    started = time.monotonic()
    try:
        markdown, blocks = parse(row["file_path"], row["filename"], row["media_type"])
        with connect() as db:
            db.execute("UPDATE documents SET status='parsed',markdown=?,blocks=?,updated_at=? WHERE id=?", (markdown, json.dumps(blocks, ensure_ascii=False), now(), document_id))
            audit(db, row["project_id"], "parse", "document", document_id, {"blocks": len(blocks)})
        logger.info("parse finished: document=%s blocks=%d elapsed=%.2fs", document_id, len(blocks), time.monotonic() - started)
    except Exception as exc:
        message = str(exc) if isinstance(exc, ParseError) else f"문서 파싱 실패: {exc}"
        logger.exception("parse failed: document=%s elapsed=%.2fs", document_id, time.monotonic() - started)
        with connect() as db: db.execute("UPDATE documents SET status='failed',error=?,updated_at=? WHERE id=?", (message, now(), document_id))


@app.post("/api/documents/{document_id}/parse", status_code=202, dependencies=[Depends(auth)])
def retry_parse(document_id: str, background: BackgroundTasks):
    with connect() as db:
        one(db, "SELECT id FROM documents WHERE id=?", (document_id,))
        db.execute("UPDATE documents SET status='queued',error=NULL,markdown=NULL,blocks='[]',result=NULL,groundings='{}',validation='[]',schema_id=NULL,approved_at=NULL,updated_at=? WHERE id=?", (now(), document_id))
    background.add_task(run_parse, document_id)
    return {"id": document_id, "status": "queued"}


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


def run_extract(document_id, schema_id):
    with connect() as db:
        doc = one(db, "SELECT * FROM documents WHERE id=?", (document_id,), json_fields=("blocks",))
        schema = schema_row(db.execute("SELECT * FROM schemas WHERE id=?", (schema_id,)).fetchone())
        db.execute("UPDATE documents SET status='extracting',error=NULL,schema_id=?,updated_at=? WHERE id=?", (schema_id, now(), document_id))
    logger.info("extract start: document=%s schema=%s", document_id, schema_id)
    started = time.monotonic()
    try:
        result, groundings = engine.extract(schema["json_schema"], doc["blocks"])
        with connect() as db: db.execute("UPDATE documents SET status='validating',result=?,groundings=?,updated_at=? WHERE id=?", (json.dumps(result, ensure_ascii=False), json.dumps(groundings, ensure_ascii=False), now(), document_id))
        issues = engine.validate(result, schema["json_schema"], groundings)
        status = "needs_review" if issues else "completed"
        with connect() as db:
            db.execute("UPDATE documents SET status=?,validation=?,updated_at=? WHERE id=?", (status, json.dumps(issues, ensure_ascii=False), now(), document_id))
            audit(db, doc["project_id"], "extract", "document", document_id, {"schema_id": schema_id, "issues": len(issues)})
        logger.info("extract finished: document=%s status=%s issues=%d elapsed=%.2fs", document_id, status, len(issues), time.monotonic() - started)
    except Exception as exc:
        logger.exception("extract failed: document=%s elapsed=%.2fs", document_id, time.monotonic() - started)
        with connect() as db: db.execute("UPDATE documents SET status='failed',error=?,updated_at=? WHERE id=?", (f"추출 실패: {exc}", now(), document_id))


@app.post("/api/documents/{document_id}/extract", status_code=202, dependencies=[Depends(auth)])
def start_extract(document_id: str, data: ExtractInput, background: BackgroundTasks):
    with connect() as db:
        doc = one(db, "SELECT project_id,status FROM documents WHERE id=?", (document_id,))
        schema = one(db, "SELECT project_id FROM schemas WHERE id=?", (data.schema_id,))
        if doc["project_id"] != schema["project_id"]: raise HTTPException(409, "문서와 스키마의 프로젝트가 다릅니다.")
        if doc["status"] not in {"parsed", "needs_review", "completed"}:
            raise HTTPException(409, "파싱 완료 후 추출할 수 있습니다.")
        db.execute("UPDATE documents SET status='queued',error=NULL,updated_at=? WHERE id=?", (now(), document_id))
    background.add_task(run_extract, document_id, data.schema_id)
    return {"id": document_id, "status": "queued"}


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


def flatten(value, prefix=""):
    output = {}
    if isinstance(value, dict):
        for key, child in value.items(): output.update(flatten(child, f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, list):
        output[prefix] = json.dumps(value, ensure_ascii=False)
    else: output[prefix] = value
    return output


@app.get("/api/documents/{document_id}/export", dependencies=[Depends(auth)])
def export(document_id: str, format: str = "json"):
    with connect() as db: doc = one(db, "SELECT filename,result FROM documents WHERE id=?", (document_id,), json_fields=("result",))
    if doc["result"] is None: raise HTTPException(409, "내보낼 추출 결과가 없습니다.")
    stem = Path(doc["filename"]).stem
    if format == "json":
        return Response(json.dumps(doc["result"], ensure_ascii=False, indent=2), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{stem}.json"'})
    if format == "csv":
        row = flatten(doc["result"])
        output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
        return Response(output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{stem}.csv"'})
    raise HTTPException(422, "format은 json 또는 csv여야 합니다.")


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
