"""저장된 OCR 블록·이미지로 verify.read 를 실제 코드 그대로 돈다(OCR·AWS 호출 없음, 재처리 끔, 표만).
한 프로세스가 한 방식(--arm)을 맡는다. <out>/<arm>/<file>.json =
{rows, first_rows, last_rows, misses, usage, elapsed_ms, calls, call_kinds, providers, statuses, finishes, chunks, turns, warnings, error}"""
import argparse
import contextvars
import itertools
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--arm", choices=["rowmajor", "asis"], required=True)
ap.add_argument("--ocr", type=Path, required=True)
ap.add_argument("--imgs", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--doc-type", default="세부내역서")
ap.add_argument("--workers", type=int, default=2)
ap.add_argument("--only", nargs="+")
ap.add_argument("--folder", default="", help="<out>/<arm>/<folder>/ 아래에 쓴다(grade_ab.py 모양)")
ap.add_argument("--max-calls", type=int, default=0, help="이 프로세스의 provider 호출 상한(0이면 없음). 넘으면 그 문서를 오류로 멈춘다")
args = ap.parse_args()
os.environ["TABLE_EXTRACT"] = args.arm
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import httpx  # noqa: E402

from backend import doctypes, engine, rules, verify  # noqa: E402

_doc = contextvars.ContextVar("doc", default=None)
_sent = itertools.count(1)


class _Local:
    """문서별 기록. 쪽 묶음 병렬 호출(engine 의 ``parallel``)은 contextvars 를 넘겨받으므로 스레드가 달라도 같은 문서 기록에 쌓인다."""
    def __getattr__(self, name):
        if _doc.get() is None:
            raise AttributeError(name)
        return getattr(_doc.get(), name)


class Budget(Exception):
    """호출 상한 초과. RuntimeError 가 아니라 engine 의 쪽 실패 처리에 잡히지 않고 문서를 멈춘다."""


_local = _Local()
_stream, _extract = httpx.Client.stream, engine.extract


@contextmanager
def _timed_stream(self, *a, **kw):
    if args.max_calls and next(_sent) > args.max_calls:
        raise Budget(f"호출 상한 {args.max_calls}회를 넘었다")
    t0 = time.monotonic()
    with _stream(self, *a, **kw) as resp:
        buf, original = bytearray(), resp.iter_bytes

        def tee(*x, **y):
            for chunk in original(*x, **y):
                buf.extend(chunk)
                yield chunk
        resp.iter_bytes = tee
        try:
            yield resp
        finally:
            try:
                body = json.loads(bytes(buf))
            except ValueError:
                body = {}
            _local.log.append({"status": resp.status_code, "ms": round((time.monotonic() - t0) * 1000), "usage": body.get("usage") or {},
                               "provider": body.get("provider"), "finish": ((body.get("choices") or [{}])[0]).get("finish_reason"),
                               "kind": (kw.get("json") or {}).get("response_format", {}).get("type")})


def _recording_extract(schema, blocks, *a, **k):
    result = _extract(schema, blocks, *a, **k)
    _local.extracts.append(result[0].get(rules.ITEM_TABLE))
    return result


httpx.Client.stream, engine.extract = _timed_stream, _recording_extract


class _Log(logging.Handler):
    def emit(self, record):
        message = record.getMessage()
        if hasattr(_local, "logs") and (record.levelno >= logging.WARNING or "rowmajor" in message or "asis로 다시" in message):
            _local.logs.append(message[:300])


logging.getLogger("backend").addHandler(_Log())
logging.getLogger("backend").setLevel(logging.INFO)


def run_doc(name):
    out = args.out / args.arm / args.folder / f"{name}.json"
    if out.exists():
        return
    saved = json.loads((args.ocr / f"{name}.json").read_text(encoding="utf-8"))
    blocks = saved["blocks"]
    tables = set(doctypes.DOC_TYPES[args.doc_type]["tables"])
    _doc.set(SimpleNamespace(log=[], logs=[], blocks=blocks, extracts=[]))
    started = time.monotonic()
    rows, error = None, None
    try:
        _, rows, _ = verify.read(str(args.imgs / name), args.doc_type, only=tables, auto_reprocess=False)
    except Exception as exc:
        error = f"{type(exc).__name__}: {str(exc)[:300]}"
    wall_ms = round((time.monotonic() - started) * 1000)
    first = _local.extracts[0] if _local.extracts else None
    misses = rules.table_misses(args.doc_type, first, rules.apply(args.doc_type, {rules.ITEM_TABLE: first}, blocks)) if first else None
    log = _local.log
    record = {"rows": rows, "first_rows": first, "last_rows": _local.extracts[-1] if _local.extracts else None, "misses": misses, "extracts": len(_local.extracts),
              "usage": {k: sum(c["usage"].get(k, 0) for c in log) for k in ("prompt_tokens", "completion_tokens")},
              "elapsed_ms": sum(c["ms"] for c in log), "wall_ms": wall_ms, "call_ms": [c["ms"] for c in log], "call_tokens": [c["usage"].get("completion_tokens") for c in log], "calls": len(log), "call_kinds": [c["kind"] for c in log],
              "providers": sorted({c["provider"] for c in log if c["provider"]}), "statuses": [c["status"] for c in log],
              "finishes": [c["finish"] for c in log], "chunks": len(engine._page_chunks(blocks, engine.ai_settings()["chunk_chars"])),
              "turns": saved.get("turns") or {}, "warnings": _local.logs, "error": error}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    print(f"{args.arm} {name} {record['elapsed_ms']}ms calls={record['calls']} misses={misses} {error or ''}", flush=True)


def main():
    verify.parse = lambda *a, **k: ("", _local.blocks)  # OCR 은 저장본을 쓴다
    docs = [p.name.removesuffix(".json") for p in sorted(args.ocr.glob("*.json"))]
    docs = [d for d in docs if not args.only or d in args.only]
    print(f"arm={args.arm} docs={len(docs)} model={engine.ai_settings()['model']} table_extract={engine.ai_settings()['table_extract']}", flush=True)
    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(run_doc, docs))


if __name__ == "__main__":
    main()
