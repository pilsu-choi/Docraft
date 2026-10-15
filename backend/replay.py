"""실패한 /api/read* 요청을 보존본(``failed/<날짜>/<rid>/``)으로 다시 보낸다.

    python -m backend.replay <보존 폴더> [--url http://localhost:8000] [--remaining-ms 180000]

``meta.json``의 엔드포인트·폼 값과 ``input.*``을 그대로 올리고 상태·본문을 출력한다. 인증이 켜져 있으면 ``DOCRAFT_API_KEY``를 쓴다.
"""

import argparse
import json
import os
from pathlib import Path

import httpx

args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
args.add_argument("folder", type=Path)
args.add_argument("--url", default="http://localhost:8000")
args.add_argument("--remaining-ms", type=int, help="저장된 시한 대신 쓸 값(원래 시한이 짧아 실패했다면 늘려 본다)")
args = args.parse_args()
meta = json.loads((args.folder / "meta.json").read_text(encoding="utf-8"))
form = {key: str(value) for key, value in meta["params"].items() if value is not None}
if args.remaining_ms is not None:
    form["remaining_ms"] = str(args.remaining_ms)
upload = next(args.folder.glob("input.*"))
headers = {"X-API-Key": os.environ["DOCRAFT_API_KEY"]} if os.getenv("DOCRAFT_API_KEY") else {}
response = httpx.post(f"{args.url}/api/{meta['endpoint']}", data=form, files={"image": (upload.name, upload.read_bytes())}, headers=headers, timeout=600)
print(response.status_code, response.text[:2000])
