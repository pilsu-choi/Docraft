"""Runtime configuration loaded without exposing secrets."""

import logging
import os
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


def setup_logging() -> None:
    """Configure the `backend` package logger once; all modules use logging.getLogger(__name__)."""
    logger = logging.getLogger("backend")
    if logger.handlers:
        return
    logger.setLevel(os.getenv("LOG_LEVEL", "DEBUG").upper())
    logger.propagate = False  # Keep separate from uvicorn's own loggers/root.
    handlers = [logging.StreamHandler()]
    log_file = os.getenv("LOG_FILE", str(Path(__file__).resolve().parents[1] / "docraft.log"))
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"))
    for handler in handlers:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    for noisy in ("httpx", "httpcore", "fitz"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


ENV_FILE = load_env()
setup_logging()


def ai_settings() -> dict:
    base_url = os.getenv("AI_BASE_URL", "").rstrip("/")
    model = os.getenv("AI_VLM_MODEL") or os.getenv("AI_MODEL", "")
    mode = os.getenv("AI_MODE", "provider")
    key = os.getenv("AI_API_KEY", "")
    configured = mode == "local" or bool(base_url and key and model)
    chunk_chars = int(os.getenv("EXTRACT_CHUNK_CHARS", "40000"))
    return {"mode": mode, "base_url": base_url, "api_key": key, "model": model, "configured": configured, "chunk_chars": chunk_chars}


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
