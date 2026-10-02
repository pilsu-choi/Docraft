"""컨테이너 안에서 실행(서비스 앱은 건드리지 않음): /tmp/vx/backend(통합 브랜치 사본)로 /tmp/vx/imgs/<묶음>/<파일>을 OCR 해
/tmp/vx/ocr/<묶음>/<파일>.json = {ocr_ms, blocks, turns} 로 저장한다. turns = 쪽 → 바로 세운 각도."""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backend import engine  # noqa: E402
from backend.parsers import parse  # noqa: E402

root = Path(__file__).parent
lock, provider, refine_calls = threading.Lock(), engine._provider, [0]  # 표 교정은 따로 스레드에서 돌아 전체 수만 센다


def counted(*a, **k):
    with lock:
        refine_calls[0] += 1
    return provider(*a, **k)


engine._provider = counted


def one(p):
    out = root / "ocr" / p.parent.name / (p.name + ".json")
    if out.exists():
        return p.name, "skip"
    out.parent.mkdir(parents=True, exist_ok=True)
    t = time.monotonic()
    try:
        _, blocks = parse(str(p), p.name, "", {"provider": "paddle"})
    except Exception as e:
        return p.name, f"ERR {type(e).__name__}: {e}"
    ms = round((time.monotonic() - t) * 1000)
    turns = {b["page"]: b["orientation"] for b in blocks if b.get("orientation")}
    out.write_text(json.dumps({"ocr_ms": ms, "blocks": blocks, "turns": turns}, ensure_ascii=False, default=str))
    return p.name, f"{ms}ms turns={turns} refine_total={refine_calls[0]}"


files = sorted(f for f in (root / "imgs").glob("*/*") if f.is_file())
with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 3) as ex:
    for name, r in ex.map(one, files):
        print(name, r, flush=True)
