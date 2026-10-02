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
    table_extract = os.getenv("TABLE_EXTRACT", "rowmajor").strip().lower()
    table_recheck_ratio = float(os.getenv("TABLE_RECHECK_RATIO", "0.6"))
    return {"mode": mode, "base_url": base_url, "api_key": key, "model": model, "configured": configured, "chunk_chars": chunk_chars, "vision": vision, "table_refine": table_refine, "reasoning": reasoning,
            "table_extract": table_extract, "table_recheck_ratio": table_recheck_ratio}


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
