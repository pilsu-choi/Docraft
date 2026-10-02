"""정답 없는 세부내역서 추가 표본 뽑기: 파일 이름 구조·확장자·쪽수로 층을 나눠 약 100건을 고르고 imgs/ 로 복사한다.
'1(개인정보O)' 폴더는 쓰지 않는다. 정답지 59건과 같은 파일은 뺀다."""
import csv
import random
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import fitz
from PIL import Image

SRC = Path("/mnt/c/Users/user/Desktop/미래에셋/데이터셋/진료비세부산정내역서-20260806T005053Z-1-001/진료비세부산정내역서/2(개인정보X)")
GOLD = Path("/home/pilsu/projects/mirae-assets/e2e/out/ab-rowmajor-1002/imgs")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/pilsu/projects/mirae-assets/e2e/out/extra-detail-1002")
TOTAL, FLOOR = 100, 3
PATTERNS = [  # (층 이름, 파일 이름 정규식) — 먼저 맞는 것
    ("KJM기관", r"_KJM\d+_"), ("9100기관", r"_9100_\d+_"), ("SA접수", r"^SA\d+_"), ("16자리-1png", r"^\d{16}-\d"),
    ("10자리", r"^\d{10}$"), ("20자리tif", r"^\d{20}$"), ("휴대폰사진", r"^\d{8}[_-]\d{4,6}"), ("캡처", r"^캡처"),
    ("13자리", r"^\d{13}$"), ("UUID", r"^[0-9A-F]{8}-"), ("한글이름", r"^[가-힣]+\d*$"),
]


def pattern(stem):
    return next((name for name, rx in PATTERNS if re.search(rx, stem)), "기타")


def pages(path):
    try:
        if path.suffix.lower() == ".pdf":
            with fitz.open(path) as doc:
                return doc.page_count
        with Image.open(path) as image:
            return getattr(image, "n_frames", 1)
    except Exception:
        return 0


def main():
    gold = {re.sub(r"^.*?(?=SA\d|\d{6})", "", p.stem) for p in GOLD.glob("*/*")}
    files = [p for p in sorted(SRC.iterdir()) if p.is_file() and p.stem not in gold and not any(p.stem.endswith(g) for g in gold)]
    strata = defaultdict(list)
    for p in files:
        ext = p.suffix.lower().replace("jpeg", "jpg")
        strata[(pattern(p.stem), ext)].append(p)
    rng = random.Random(1002)
    quota = {k: min(len(v), FLOOR) for k, v in strata.items()}
    rest = TOTAL - sum(quota.values())
    big = {k: len(v) - quota[k] for k, v in strata.items() if len(v) > quota[k]}
    for k, extra in big.items():
        quota[k] += round(rest * extra / sum(big.values()))
    picked = []
    for key in sorted(strata):
        group = strata[key][:]
        rng.shuffle(group)
        # 여러 쪽 파일을 먼저 한 건 넣어 다중 쪽을 놓치지 않는다
        group.sort(key=lambda p: -min(pages(p), 2) if key[1] in (".pdf", ".tif") else 0)
        picked += [(key, p) for p in group[:quota[key]]]
    (OUT / "imgs").mkdir(parents=True, exist_ok=True)
    with open(OUT / "sample.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "pattern", "ext", "pages", "stratum_size"])
        for (pat, ext), p in picked:
            shutil.copy2(p, OUT / "imgs" / p.name)
            w.writerow([p.name, pat, ext, pages(p), len(strata[(pat, ext)])])
    print(f"files={len(files)} strata={len(strata)} picked={len(picked)}")
    for key in sorted(strata):
        print(key, len(strata[key]), quota[key])


if __name__ == "__main__":
    main()
