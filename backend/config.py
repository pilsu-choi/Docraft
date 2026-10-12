"""Runtime configuration loaded without exposing secrets."""

import contextvars
import logging
import os
import re
import uuid
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse


def _main_checkout() -> Path | None:
    git_file = Path(__file__).resolve().parents[1] / ".git"
    if git_file.is_file():
        marker = git_file.read_text().strip()
        if marker.startswith("gitdir:"):
            git_dir = Path(marker.removeprefix("gitdir:").strip()).resolve()
            if git_dir.parent.name == "worktrees":
                return git_dir.parents[2]
    return None


def _load(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key.isidentifier():
            os.environ.setdefault(key, value.strip("'\""))


def load_env() -> Path | None:
    override = os.getenv("DOCRAFT_ENV_FILE")
    candidates = [Path(override).expanduser()] if override else []
    candidates.extend([Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env"])
    main = _main_checkout()
    if main:
        candidates.append(main / ".env")
    for candidate in candidates:
        if candidate.is_file():
            _load(candidate)
            return candidate
    return None


# 로그 한 줄이 어느 요청·작업의 것인지. /api/verify 가 동시에 여러 건 돌면 이것 없이는 중간 줄(LLM 호출 등)을 가를 수 없다.
_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("docraft_request_id", default="-")
_UNSAFE = re.compile(r"[^A-Za-z0-9._:/=-]")


def request_id() -> str:
    return _request_id.get()


def new_request_id(incoming: str | None = None) -> str:
    """호출자가 준 X-Request-ID(하네스는 job·doc id)를 로그에 안전한 모양으로, 없으면 새로 만든다."""
    cleaned = _UNSAFE.sub("", incoming or "")[:64]
    return cleaned or uuid.uuid4().hex[:12]


@contextmanager
def bind_request(rid: str):
    """이 블록(과 asyncio.to_thread 로 넘긴 작업)의 모든 로그 줄에 [rid] 를 붙인다."""
    token = _request_id.set(rid)
    try:
        yield rid
    finally:
        _request_id.reset(token)


class _RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.rid = _request_id.get()
        return True


def setup_logging() -> None:
    """Configure the `backend` package logger once; all modules use logging.getLogger(__name__)."""
    logger = logging.getLogger("backend")
    if logger.handlers:
        return
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False  # Keep separate from uvicorn's own loggers/root.
    handlers = [logging.StreamHandler()]
    log_file = os.getenv("LOG_FILE", str(Path(__file__).resolve().parents[1] / "docraft.log"))
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"))
    for handler in handlers:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(rid)s] %(message)s"))
        handler.addFilter(_RequestIdFilter())
        logger.addHandler(handler)
    for noisy in ("httpx", "httpcore", "fitz"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


ENV_FILE = load_env()
setup_logging()


def limit(name: str, default: int, ceiling: int) -> int:
    """정수 환경변수를 [0, ceiling]으로 자른 값. 숫자가 아니면 default."""
    try:
        return max(0, min(int(os.getenv(name, default)), ceiling))
    except ValueError:
        return default


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() not in {"false", "0", "no", "off"}


def ai_settings() -> dict:
    base_url = os.getenv("AI_BASE_URL", "").rstrip("/")
    model = os.getenv("AI_VLM_MODEL") or os.getenv("AI_MODEL", "")
    mode = os.getenv("AI_MODE", "provider")
    key = os.getenv("AI_API_KEY", "")
    configured = mode == "local" or bool(base_url and key and model)
    chunk_chars = int(os.getenv("EXTRACT_CHUNK_CHARS", "40000"))
    # Attach the page image to provider calls so the model reads the table layout from the document itself.
    vision = _flag("AI_VISION", "true")
    # Correct OCR table cell text against the table image, keeping the OCR model's cell structure.
    table_refine = _flag("TABLE_REFINE", "false")
    # Some VLMs (e.g. qwen3.5) default reasoning mode on, turning a 10-30s call into 200-500s; off disables it.
    reasoning = os.getenv("AI_REASONING", "off").strip().lower() == "on"
    # How /api/read·verify reads table fields first: asis = one JSON object, rowmajor = positional rows per table, re-read asis
    # when the share of broken 세부내역서 rows (row arithmetic, all amounts blank, misfit values) reaches TABLE_RECHECK_RATIO.
    # Input-integrity and page/row repeat evidence only lands in issue_codes; true also sends the affected confirmed values to RECHECK.
    integrity_review = _flag("INTEGRITY_REVIEW", "false")
    table_extract = os.getenv("TABLE_EXTRACT", "band").strip().lower()
    # band: 한 쪽에 긴 항목 표가 있는 유형만(BAND_DOC_TYPES, band.PROFILES에 설정이 있는 진료비영수증·세부내역서) 1쪽 문서의 표를 가로 띠로
    # 잘라 읽는다. 진료비영수증은 표 위치를 먼저 찾아 BAND_STRIPS개로, 세부내역서는 위치 찾기 없이 OCR 행 경계에서 약 12행씩 자른다.
    # 기본은 진료비영수증만, 세부내역서는 "진료비영수증,세부내역서"로 켠다. 목록 밖 유형·여러 쪽 문서는 rowmajor.
    band_doc_types = tuple(name.strip() for name in os.getenv("BAND_DOC_TYPES", "진료비영수증").split(",") if name.strip())
    # 비우면 보내지 않는다. 표를 띠로 읽을 때 같은 행이 반복되는 것을 줄이려 1.05 정도를 쓴다.
    penalty = os.getenv("REPETITION_PENALTY", "").strip()
    # 1보다 크면 다시 읽지 않는다(기본 — 2026-10-12, 다시 읽기가 VLM 호출 1회를 순차로 더해 지연을 늘린다). 켤 때는 0.6을 쓴다.
    table_recheck_ratio = float(os.getenv("TABLE_RECHECK_RATIO", "2"))
    # 진료비영수증 band 읽기 뒤 금액 층이 양식 칸선에서 통째로 밀려 찍힌 인쇄를 OCR 줄 좌표로 문서 단위에서 되돌린다(print_register).
    print_register = _flag("PRINT_REGISTER", "false")
    # band 띠 프롬프트에 쪼개 인쇄된 머리글 이어 읽기·비급여 묶음 제목 안내를 붙인다(band.HEADER_NOTE). 기본 켬(2026-10-12 AWS 하네스 30건·10건 +1칸씩, 깨짐 0).
    band_header_note = _flag("BAND_HEADER_NOTE", "true")
    # band 읽기 지연 줄이기. prelocate: OCR과 동시에 바로 선 쪽 이미지로 표 위치를 찾고 OCR이 쪽을 돌리지 않았으면 그 답을 쓴다(결과 동일).
    # speculate: 위치 응답을 기다리지 않고 금액산정 키를 뺀 나머지 필드를 먼저 읽고, 금액산정 상자가 없으면 버리고 지금처럼 다시 읽는다(결과 동일).
    # strips: 항목 표를 자르는 띠 수. strip_edge(BAND_STRIP_EDGE, px): 세부내역서 OCR 행 띠 크롭을 원본 해상도까지 그리는 긴 변 상한(0=끔, 기존
    # VISION_MAX_EDGE·배율 그대로). dump_dir(BAND_DUMP_DIR, 진단용): 띠 읽기에 보낸 이미지·프롬프트·응답을 남길 폴더(비우면 끔).
    # compact_reply: 띠·금액산정·나머지 필드 응답을 한 줄 JSON·상한 토큰으로 줄인다(응답이 달라질 수 있어 기본 끔).
    return {"band_prelocate": _flag("BAND_PRELOCATE", "false"), "band_speculate": _flag("BAND_SPECULATE", "false"),
            "band_strips": max(1, limit("BAND_STRIPS", 3, 8)), "band_strip_edge": limit("BAND_STRIP_EDGE", 0, 8000) or None,
            "band_dump_dir": os.getenv("BAND_DUMP_DIR", "").strip() or None, "band_strip_rows": limit("BAND_STRIP_ROWS", 0, 60) or None, "compact_reply": _flag("COMPACT_REPLY", "false"), "mode": mode, "base_url": base_url, "api_key": key, "model": model, "configured": configured, "chunk_chars": chunk_chars, "vision": vision, "table_refine": table_refine, "reasoning": reasoning,
            "integrity_review": integrity_review, "table_extract": table_extract, "band_doc_types": band_doc_types,
            "repetition_penalty": float(penalty) if penalty else None, "table_recheck_ratio": table_recheck_ratio, "print_register": print_register, "band_header_note": band_header_note}


def ocr_settings() -> dict:
    base_url = os.getenv("PADDLEOCR_BASE_URL", "").rstrip("/")
    token = os.getenv("PADDLEOCR_ACCESS_TOKEN", "")
    provider = os.getenv("PARSE_PROVIDER", "library").lower()
    return {
        "provider": provider,
        "base_url": base_url,
        # Plain PP-OCRv5 pipeline used only for text line boxes; empty disables line grounding.
        "lines_url": os.getenv("PADDLEOCR_LINES_URL", "").rstrip("/"),
        "token": token,
        "model": os.getenv("PADDLEOCR_MODEL", "PaddleOCR-VL-1.6-0.9B"),
        "timeout": float(os.getenv("PADDLEOCR_TIMEOUT", "600")),
        # Undecided page orientation is settled by re-reading the page at the candidate turns and comparing OCR scores.
        "orientation_score": _flag("ORIENTATION_SCORE_CHECK", "1"),
        # A tilted page (up to 45 degrees; past that it is a quarter turn away) is rotated straight in the image the model sees.
        "page_deskew": _flag("PAGE_DESKEW", "1"),
        "configured": provider == "paddle" and bool(base_url),
    }


def public_ai_settings() -> dict:
    settings = ai_settings()
    host = urlparse(settings["base_url"]).hostname
    ocr = ocr_settings()
    return {
        "configured": settings["configured"],
        "mode": settings["mode"],
        "provider": host,
        "model": settings["model"] or None,
        "ocr": {
            "mode": "paddle" if ocr["provider"] == "paddle" else "library",
            "configured": ocr["configured"],
            "provider": urlparse(ocr["base_url"]).hostname if ocr["provider"] == "paddle" else "local/native",
            "model": ocr["model"] if ocr["provider"] == "paddle" else None,
            "ready": ocr["configured"],
        },
    }
