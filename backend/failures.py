"""/api/read* 실패의 분류·한 줄 요약·재현용 입력 보존.

운영자가 터미널을 사진으로 찍어 보내므로 실패마다 한 줄(``read failed: ...``)에 원인을 모두 담는다. 시간 초과는 어떤 예외 종류든
(builtin·asyncio TimeoutError, httpx.*Timeout, 자리 대기, 요청 시한) 408, 상위 서버(VLM·OCR)의 HTTP 오류·연결 실패는 502다.
연결 거부도 502다: 408/502 모두 호출자(하네스)에서는 같은 "판독 불가" 처리이고, 503은 재시도 지시로 읽혀 쓰지 않는다.
"""

import glob
import json
import logging
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from fastapi import HTTPException

from . import latency
from .config import limit, request_id
from .db import ROOT

logger = logging.getLogger("docraft.failures")
FAILED = ROOT / "failed"


class ProviderError(RuntimeError):
    """VLM provider가 준 답을 쓸 수 없다. ``kind``: http_<코드> | format | truncated."""

    def __init__(self, message, kind):
        super().__init__(message)
        self.kind = kind


def _chain(exc):
    while exc is not None:
        yield exc
        exc = exc.__cause__


def classify(exc):
    """``(HTTP 상태, 종류, 적용한 timeout 초 또는 None)``. 원인 사슬 전체를 본다 — ParseError 같은 래퍼 밑의 시간 초과도 408이다."""
    causes = list(_chain(exc))
    for cause in causes:
        if isinstance(cause, latency.Timeout):
            return 408, cause.kind, cause.timeout_s
        if isinstance(cause, (TimeoutError, httpx.TimeoutException)):
            return 408, "deadline" if isinstance(cause, TimeoutError) else "call_timeout", None
    for cause in causes:
        if isinstance(cause, ProviderError):
            return 502, cause.kind, None
        if isinstance(cause, json.JSONDecodeError):  # VLM 답이 JSON이 아님(요청 본문 해석 오류는 라우트가 먼저 422로 거른다)
            return 502, "format", None
        if isinstance(cause, httpx.HTTPStatusError):
            return 502, f"http_{cause.response.status_code}", None
        if isinstance(cause, httpx.TransportError):
            return 502, "connect" if isinstance(cause, httpx.ConnectError) else "transport", None
    return (422, "input", None) if isinstance(exc, ValueError) else (502, "error", None)


def response(exc, label, client_input=True):
    """``exc``를 HTTPException으로: 시간 초과 408(종류 포함), 입력 오류 422(``client_input``이 아니면 502), 그 밖에 502."""
    status, kind, timeout_s = classify(exc)
    if status == 408:
        return HTTPException(408, f"시간 초과 ({kind}{f', {timeout_s}s' if timeout_s else ''}): {exc}")
    if status == 422 and client_input:
        return HTTPException(422, str(exc))
    return HTTPException(502, f"{label}에 실패했습니다 ({kind}): {exc}")


def prune(root=None):
    """보존 일수(``FAILED_KEEP_DAYS``)가 지난 날짜 폴더를 지우고, 총량이 ``FAILED_MAX_MB``를 넘으면 오래된 건부터 지운다."""
    root = root or FAILED
    if not root.is_dir():
        return
    cutoff = (datetime.now() - timedelta(days=limit("FAILED_KEEP_DAYS", 7, 3650))).strftime("%Y%m%d")
    for day in root.iterdir():
        if day.name <= cutoff:
            shutil.rmtree(day, ignore_errors=True)
    entries = []
    for entry in glob.glob(str(root / "*" / "*")):  # glob 은 다른 파드가 지운 폴더를 건너뛴다(PVC 공유)
        try:
            entry = Path(entry)
            entries.append((entry.stat().st_mtime, entry, sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())))
        except FileNotFoundError:
            continue
    entries.sort(key=lambda item: item[0])
    total, cap = sum(size for *_, size in entries), limit("FAILED_MAX_MB", 2048, 1_000_000) << 20
    for _, entry, size in entries:
        if total <= cap:
            break
        shutil.rmtree(entry, ignore_errors=True)
        total -= size


@dataclass
class Call:
    """/api/read* 한 건의 실패 보고용 문맥: 어느 엔드포인트가 어떤 입력·시한으로 시작했는지."""
    endpoint: str
    doc_type: str | None
    remaining_ms: int | None
    deadline: float
    params: dict = field(default_factory=dict)  # 재현에 필요한 폼 값(문자열)
    started: float = field(default_factory=time.monotonic)
    upload: tuple[str, bytes] | None = None

    def snapshot(self, path):
        """실패한 업로드를 임시폴더가 지워지기 전에 메모리에 잡아 둔다(보존이 켜졌을 때만)."""
        if limit("FAILED_KEEP_DAYS", 7, 3650):
            self.upload = (Path(path).suffix, Path(path).read_bytes())

    def fail(self, exc, stages, label):
        """실패 한 줄을 남기고, 입력을 보존하고, 응답할 HTTPException을 돌려준다. 호출자가 ``raise ... from exc``로 올린다."""
        status, kind, timeout_s = classify(exc)
        info = {"rid": request_id(), "endpoint": self.endpoint, "doc_type": self.doc_type, "status": status, "stage": stages.get("_stage"),
                "kind": kind, "timeout_s": timeout_s, "budget_ms": self.remaining_ms,
                "remaining_s": round(self.deadline - time.monotonic(), 1), "elapsed_ms": round((time.monotonic() - self.started) * 1000),
                "vlm_calls": stages.get("vlm_calls", 0), "upstream": stages.get("_upstream")}
        line = " ".join(f"{key}={value}" for key, value in info.items() if value not in (None, ""))
        totals = " ".join(f"{key}={value}" for key, value in stages.items() if not key.startswith("_") and isinstance(value, (int, float)))
        logger.log(logging.ERROR if kind == "error" else logging.WARNING, "%s failed: %s | %s: %s | %s", self.endpoint, line,
                   type(exc).__name__, exc, totals, exc_info=exc if kind == "error" else None)
        logger.debug("%s failure traceback", self.endpoint, exc_info=exc)
        self._save(info, line, stages, exc)
        return response(exc, label)

    def _save(self, info, line, stages, exc):
        """입력·폼 값·실패 한 줄·받아 둔 VLM 응답을 ``failed/<날짜>/<rid>/``에 둔다. 저장이 실패해도 원래 오류를 가리지 않는다."""
        if self.upload is None:
            return
        try:
            folder = FAILED / datetime.now().strftime("%Y%m%d") / (re.sub(r"[^\w.-]", "_", info["rid"])[:80] or "unknown")
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"input{self.upload[0]}").write_bytes(self.upload[1])
            meta = {**info, "line": line, "error": f"{type(exc).__name__}: {exc}", "params": self.params, "saved_at": datetime.now().isoformat()}
            (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            (folder / "vlm_replies.json").write_text(json.dumps(stages.get("_vlm_replies", []), ensure_ascii=False, indent=1), encoding="utf-8")
            prune()
        except Exception as save_error:
            logger.warning("failed-input save skipped: %s", save_error)
