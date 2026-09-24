"""harness-v2 e2e 폴더(샘플·AO 응답·정답지)로 /api/verify 최종 정확도를 AO 단독과 같은 채점기로 비교한다.

    python scripts/verify_e2e.py run   --e2e <e2e 폴더> --out data/verify/e2e-20260924 --url http://localhost:13000
    python scripts/verify_e2e.py grade --e2e <e2e 폴더> --out data/verify/e2e-20260924

채점은 e2e 폴더의 ``make_report.compare``를 그대로 쓴다. AO 쪽은 e2e ``out/harness``(하네스가 값을 바꾸지 않아 AO 값과 같음),
Docraft 쪽은 ``--out/<문서종류>/<파일명>.harness.json``(``/api/verify`` 응답)을 읽는다.
"""
import argparse
import collections
import csv
import importlib.util
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

DOC_TYPES = ("세부내역서", "진료비영수증")


def samples(e2e: Path):
    """AO 처리가 끝난 (문서종류, 이미지, AO 응답) 목록."""
    for doc_type in DOC_TYPES:
        for image in sorted((e2e / f"{doc_type} 테스트 샘플").iterdir()):
            ao = e2e / "out" / "ocr" / doc_type / f"{image.name}.json"
            if ao.exists() and json.loads(ao.read_text(encoding="utf-8")).get("status") == "completed":
                yield doc_type, image, ao


def run(args):
    key = os.getenv("DOCRAFT_API_KEY", "")
    todo = [(t, i, a) for t, i, a in samples(args.e2e) if not (args.out / t / f"{i.name}.harness.json").exists()]
    print(f"[run] {len(todo)}건 요청")

    def one(item):
        doc_type, image, ao = item
        target = args.out / doc_type / f"{image.name}.harness.json"
        with image.open("rb") as fh:
            res = httpx.post(f"{args.url}/api/verify", headers={"X-API-Key": key}, timeout=1800,
                             files={"image": (image.name, fh)},
                             data={"ao_result": ao.read_text(encoding="utf-8"), "doc_type": doc_type})
        if res.status_code != 200:
            return f"실패 {res.status_code} {image.name}: {res.text[:200]}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(res.text, encoding="utf-8")
        return f"완료 {image.name} {res.elapsed.total_seconds():.0f}s"

    with ThreadPoolExecutor(args.workers) as pool:
        for line in pool.map(one, todo): print(line, flush=True)


def grade(args):
    spec = importlib.util.spec_from_file_location("make_report", args.e2e / "make_report.py")
    report = sys.modules["make_report"] = importlib.util.module_from_spec(spec)  # dataclass가 sys.modules에서 모듈을 찾는다
    spec.loader.exec_module(report)
    load = report.load

    def blank_dash(path):
        """정답지가 코드 칸에 인쇄된 '-'를 적으면 결과의 빈 코드와 짝이 안 맞아 같은 행이 '결과에만 있는 행'이 된다."""
        data = load(path)
        for doc in (data or {}).get("documents") or []:
            for table in doc.get("extracted_tables") or []:
                for cell in (cell for row in table.get("rows") or [] for cell in row):
                    if cell.get("key") in ("EDI코드", "원내코드") and str(cell.get("value") or "").strip() == "-":
                        cell["value"] = ""
        return data

    report.load = blank_dash
    files = [(t, i) for t, i, _ in samples(args.e2e) if (args.out / t / f"{i.name}.harness.json").exists()]
    verdicts = {}
    for name, folder in (("ao", args.e2e / "out" / "harness"), ("docraft", args.out)):
        report.HARNESS_DIR = folder
        verdicts[name] = {(r.file, r.item_id): r for t, i in files for r in report.compare(t, i).rows}
    def absent(row):
        """다른 쪽에만 있는 칸 — compare는 정답의 빈 행에 결과 행이 없으면 건너뛰므로, 이쪽은 그 행이 없는 것으로 판정한다."""
        amount = (row.area == "표" and row.key not in report.NON_AMOUNT_KEYS) or row.container in report.AMOUNT_GROUPS \
            or row.key in report.AMOUNT_FIELDS
        return report.judge(row.answer, None, amount, row.key)

    doc_of = {i.name: t for t, i in files}
    summary, changes = {}, []
    for file, item in verdicts["ao"].keys() | verdicts["docraft"].keys():
        ao, dc = verdicts["ao"].get((file, item)), verdicts["docraft"].get((file, item))
        pair = {"ao": ao.auto if ao else absent(dc), "docraft": dc.auto if dc else absent(ao)}
        for name, verdict in pair.items():
            summary.setdefault(doc_of[file], {}).setdefault(name, collections.Counter())[verdict] += 1
        if (ao and ao.final) != (dc and dc.final):
            changes.append([doc_of[file], file, item, (ao or dc).answer, ao and ao.final, dc and dc.final, pair["ao"], pair["docraft"]])
    out = {}
    for doc_type, by in summary.items():
        for name, c in by.items():
            scored = sum(c[v] for v in report.SCORED)
            out[f"{doc_type}/{name}"] = {**{v: c[v] for v in report.SCORED}, "평가": scored,
                                         "정확도": round(c[report.MATCH] / scored * 100, 2)}
            print(f"{doc_type:8} {name:8} {dict((v, c[v]) for v in report.SCORED)} → {out[f'{doc_type}/{name}']['정확도']}%")
    print(f"문서 {len(files)}건, Docraft가 바꾼 칸 {len(changes)}")
    (args.out / "grade.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    with (args.out / "changes.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        csv.writer(fh).writerows([["문서종류", "파일", "칸", "정답", "AO", "Docraft", "AO판정", "Docraft판정"], *changes])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["run", "grade"])
    parser.add_argument("--e2e", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--url", default="http://localhost:13000")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    sys.exit(run(args) if args.cmd == "run" else grade(args))
