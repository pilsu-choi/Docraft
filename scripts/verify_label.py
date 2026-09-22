"""AO(Agentic OCR 2.0) 교차검증용 정답셋(라벨) 구축 스크립트.

문서 유형 4종(진단서·소견서·진료비영수증·세부내역서)의 이미지를 VLM(라벨링 모델 ≠ 추출 모델)에게
이미지만 보여주고(OCR 텍스트 없이) 필드값을 읽게 해 ``data/verify/labels/<doc_type>/<stem>.json``에 저장한다.

라벨 파일 형식::

    {
      "doc_type": "진단서", "image": "<절대경로>", "grade": "gold"|"silver",
      "labeler": "<모델 id>", "ao": "<AO json 절대경로>",   # gold만
      "fields": {"진단일": "20230228", ..., "병명내역": [{"병명코드": "R634", "병명": "..."}]}
    }

``fields``는 정규 dict: 스칼라 필드는 최상위 키 → 문자열|null, 표는 표 key → 행(dict) 목록.
키는 AO 응답의 ``key``를 그대로 쓴다(``backend.doctypes.schema``가 구현되면 그 스키마를,
아직이면 AO 예시 JSON에서 뽑은 fallback 스키마를 쓴다 — 이 fallback은 ``scripts/verify_eval.py``의
raw 단계에서도 그대로 가져다 쓴다).

사용법::

    ../../.venv/bin/python scripts/verify_label.py                       # 4종 전부: gold 4 + silver 32
    ../../.venv/bin/python scripts/verify_label.py --only-gold
    ../../.venv/bin/python scripts/verify_label.py --doc-type 진단서 --doc-type 소견서
    ../../.venv/bin/python scripts/verify_label.py --per-type 4 --force
    ../../.venv/bin/python scripts/verify_label.py --model anthropic/claude-sonnet-4.5
    ../../.venv/bin/python scripts/verify_label.py --conform-only   # 기존 라벨을 AO 관례로 정합만

동작 확인(이미 만든 라벨은 건너뜀)::

    ../../.venv/bin/python scripts/verify_label.py --doc-type 진단서 --per-type 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo(worktree) root -> `backend` 패키지 임포트용

from backend.config import ai_settings  # noqa: E402
from backend.engine import _page_images, _provider, _user  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("verify_label")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data" / "files"
LABELS_ROOT = REPO_ROOT / "data" / "verify" / "labels"
AO_ROOT = Path("/home/pilsu/projects/mirae-assets/harness-v2/docs/agentic-ocr-2.0.1-results")

DOC_TYPES = ["진단서", "소견서", "진료비영수증", "세부내역서"]
MODEL_CANDIDATES = ["anthropic/claude-sonnet-4.5", "google/gemini-2.5-pro", "openai/gpt-5"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
TIF_EXTS = {".tif", ".tiff"}
WORKERS = 4
CALL_TIMEOUT = 180

LABEL_SYSTEM = (
    "당신은 한국 의료 문서(진단서·소견서·진료비영수증·세부내역서)를 판독하는 전문가다. "
    "첨부된 문서 이미지 원본만 보고 아래 JSON Schema의 모든 필드를 채워라. OCR 텍스트는 제공되지 않으니 "
    "이미지에 인쇄되거나 손으로 적힌 내용을 있는 그대로 읽어라. 지어내거나 다른 문서 지식으로 추측하지 마라.\n"
    "- 날짜는 YYYYMMDD 8자리 숫자 문자열로 통일한다(예: 2023년 2월 28일 -> 20230228).\n"
    "- 금액은 콤마·원 등 기호를 뺀 숫자만 있는 문자열로 적는다.\n"
    "- 문서에 없거나 읽을 수 없는 스칼라 필드는 null로 남긴다.\n"
    "- 표 필드는 실제 데이터 행만 배열로 담고, 합계·소계 행은 제외한다. 행이 없으면 빈 배열로 남긴다.\n"
    "- 스키마에 없는 키를 추가하지 말고, 스키마의 키 구조를 그대로 따르는 JSON 객체 하나만 반환한다."
)


# --------------------------------------------------------------------------------------
# AO 예시 -> fallback 스키마 (doctypes.schema 미구현 시 이 스키마를 쓴다; verify_eval.py도 재사용)
# --------------------------------------------------------------------------------------

def ao_example(doc_type: str) -> tuple[Path, Path]:
    """유형별 AO 예시의 (json 경로, 동봉 이미지 경로). 디렉터리마다 json 1개·이미지 1개뿐이다."""
    directory = AO_ROOT / doc_type
    if not directory.is_dir():
        raise FileNotFoundError(f"AO 예시 디렉터리가 없습니다: {directory}")
    json_paths = sorted(directory.glob("*.json"))
    image_paths = sorted(p for p in directory.glob("*") if p.suffix.lower() in IMAGE_EXTS)
    if not json_paths or not image_paths:
        raise FileNotFoundError(f"AO 예시 json/이미지를 찾지 못했습니다: {directory}")
    return json_paths[0], image_paths[0]


def ao_document(json_path: Path) -> dict:
    """AO 응답 json에서 documents[0]."""
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    return data["documents"][0]


def fallback_schema(doc_type: str) -> dict:
    """유형의 AO 예시 json에서 키 목록을 뽑아 만든 JSON Schema. 순서는 AO 응답의 필드 순서를 따른다."""
    json_path, _ = ao_example(doc_type)
    doc = ao_document(json_path)
    props: dict = {}
    for item in doc.get("extracted_fields", []):
        props.setdefault(item["key"], {"type": ["string", "null"]})
    for group in doc.get("extracted_groups", []):
        for item in group.get("fields", []):
            props.setdefault(item["key"], {"type": ["string", "null"]})
    for table in doc.get("extracted_tables", []):
        headers = table.get("headers") or [cell["key"] for cell in (table.get("rows") or [[]])[0]]
        col_props = {h: {"type": ["string", "null"]} for h in headers}
        props[table["key"]] = {"type": "array", "items": {"type": "object", "properties": col_props}}
    return {"type": "object", "title": doc_type, "properties": props}


def schema_for(doc_type: str) -> dict:
    """``backend.doctypes.schema``가 구현되어 있으면 그것을, 아니면 fallback_schema를 쓴다."""
    try:
        from backend import doctypes

        return doctypes.schema(doc_type)
    except NotImplementedError:
        pass
    except Exception as exc:  # pragma: no cover - 방어적 fallback
        logger.warning("doctypes.schema(%s) 호출 실패, fallback 스키마 사용: %s", doc_type, exc)
    return fallback_schema(doc_type)


# --------------------------------------------------------------------------------------
# 라벨링 모델 선택 — 요청 body의 model 키만 얇게 바꿔치기(ai_settings 자체는 건드리지 않음)
# --------------------------------------------------------------------------------------

def resolve_model(explicit: str | None) -> str:
    if explicit:
        return explicit
    settings = ai_settings()
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(f"{settings['base_url']}/models", headers={"Authorization": f"Bearer {settings['api_key']}"})
            response.raise_for_status()
            available = {item["id"] for item in response.json().get("data", [])}
        for candidate in MODEL_CANDIDATES:
            if candidate in available:
                return candidate
        logger.warning("후보 모델(%s) 중 사용 가능한 것이 없어 설정된 모델을 씁니다.", MODEL_CANDIDATES)
    except Exception as exc:
        logger.warning("모델 목록 조회 실패(%s), 설정된 모델을 씁니다.", exc)
    return settings["model"]


@contextmanager
def model_override(model: str | None):
    """추출 모델(qwen3-vl-32b)과 라벨링 모델이 같으면 순환 평가가 되므로, ``_provider``가 보내는
    요청 body의 ``model`` 키만 가로채 바꾼다. engine.py나 ai_settings()는 건드리지 않는다."""
    extract_model = ai_settings()["model"]
    if not model or model == extract_model:
        yield
        return
    original_post = httpx.Client.post

    def patched_post(self, url, *args, **kwargs):
        body = kwargs.get("json")
        if isinstance(body, dict) and "model" in body:
            kwargs["json"] = {**body, "model": model}
        return original_post(self, url, *args, **kwargs)

    httpx.Client.post = patched_post
    try:
        yield
    finally:
        httpx.Client.post = original_post


# --------------------------------------------------------------------------------------
# 라벨링
# --------------------------------------------------------------------------------------

_NULLISH = {"", "null", "n/a", "none", "-", "해당없음", "없음"}


def _clean_scalar(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        return text if text and text.lower() not in _NULLISH else None
    return None


def _clean_result(schema: dict, result: dict) -> dict:
    out: dict = {}
    for key, prop in schema.get("properties", {}).items():
        value = result.get(key) if isinstance(result, dict) else None
        if prop.get("type") == "array":
            columns = prop.get("items", {}).get("properties", {})
            rows = value if isinstance(value, list) else []
            out[key] = [{col: _clean_scalar(row.get(col)) for col in columns} for row in rows if isinstance(row, dict)]
        else:
            out[key] = _clean_scalar(value)
    return out


def conform(doc_type: str, fields: dict) -> dict:
    """라벨을 AO 응답 관례에 맞춘다 — 주민번호에서 성별·생년월일, 세부내역서 코드 열·급여 칸·종료일자 등.

    관례 자체는 ``backend.rules.derive``가 한 벌로 갖고 있으므로 그대로 부른다(여기서 다시 구현하지 않는다).
    읽은 값을 고치지는 않고, 문서에서 읽을 수 있는 자리를 AO와 같은 규칙으로 채우기만 한다.
    """
    try:
        from backend import rules

        return rules.derive(doc_type, deepcopy(fields))
    except (NotImplementedError, ImportError):
        return fields


def conform_all(doc_types: list[str]) -> int:
    """이미 만들어 둔 라벨에 ``conform``을 적용하고 바뀐 값의 수를 돌려준다."""
    changed = 0
    for doc_type in doc_types:
        for path in sorted((LABELS_ROOT / doc_type).glob("*.json")):
            label = json.loads(path.read_text(encoding="utf-8"))
            before = label["fields"]
            after = conform(doc_type, before)
            diff = sum(json.dumps(before.get(key), ensure_ascii=False) != json.dumps(value, ensure_ascii=False)
                       for key, value in after.items())
            if not diff:
                continue
            changed += diff
            label["fields"] = after
            path.write_text(json.dumps(label, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("conform: %s/%s -> 필드 %d개 변경", doc_type, path.name, diff)
    return changed


def _evenly_spaced(items: list, n: int) -> list:
    if n <= 0 or not items:
        return []
    if n >= len(items):
        return list(items)
    step = len(items) / n
    chosen, seen = [], set()
    for i in range(n):
        idx = min(int(i * step), len(items) - 1)
        if idx not in seen:
            seen.add(idx)
            chosen.append(items[idx])
    idx = 0
    while len(chosen) < n and idx < len(items):
        if idx not in seen:
            seen.add(idx)
            chosen.append(items[idx])
        idx += 1
    return chosen


def pick_silver(doc_type: str, n: int = 8, min_tif: int = 3) -> list[Path]:
    """유형 샘플 디렉터리(재귀)에서 파일명 정렬 후 균등 간격으로 n장 고른다(tif 최소 min_tif장, 재현 가능)."""
    root = DATA_ROOT / f"{doc_type}_samples"
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    tifs = [p for p in files if p.suffix.lower() in TIF_EXTS]
    others = [p for p in files if p.suffix.lower() not in TIF_EXTS]
    picked_tif = _evenly_spaced(tifs, min(min_tif, len(tifs)))
    picked_other = _evenly_spaced(others, n - len(picked_tif))
    return sorted(picked_tif + picked_other)[:n]


def _label_path(doc_type: str, image_path: Path) -> Path:
    directory = LABELS_ROOT / doc_type
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{image_path.stem}.json"
    if path.exists():
        try:
            existing_image = json.loads(path.read_text(encoding="utf-8")).get("image", "")
        except Exception:
            existing_image = ""
        if existing_image and existing_image != str(image_path.resolve()):
            digest = hashlib.sha1(str(image_path).encode()).hexdigest()[:8]
            path = directory / f"{image_path.stem}-{digest}.json"
    return path


def label_one(doc_type: str, image_path: Path, schema: dict, model: str, grade: str, force: bool, ao_path: Path | None = None):
    path = _label_path(doc_type, image_path)
    if path.exists() and not force:
        return "skip", path, None
    try:
        images = _page_images(str(image_path), [1])
        if not images:
            raise RuntimeError(f"이미지 렌더링 실패/미지원 형식: {image_path.suffix}")
        user_text = f"Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n위 스키마의 각 필드 값을 첨부된 문서 이미지에서 그대로 읽어 채워라."
        messages = [{"role": "system", "content": LABEL_SYSTEM}, _user(user_text, images)]
        raw = _provider(messages, timeout=CALL_TIMEOUT)
        fields = conform(doc_type, _clean_result(schema, raw))
        label = {"doc_type": doc_type, "image": str(image_path.resolve()), "grade": grade, "labeler": model, "fields": fields}
        if ao_path is not None:
            label["ao"] = str(ao_path.resolve())
        path.write_text(json.dumps(label, ensure_ascii=False, indent=2), encoding="utf-8")
        return "ok", path, None
    except Exception as exc:
        logger.error("라벨링 실패: doc_type=%s image=%s error=%s", doc_type, image_path.name, exc)
        return "error", path, exc


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--doc-type", action="append", choices=DOC_TYPES, help="반복 지정 가능. 기본은 4종 전부.")
    parser.add_argument("--per-type", type=int, default=8, help="유형별 silver 라벨 수 (기본 8)")
    parser.add_argument("--model", default=None, help="라벨링 모델 id (기본: OpenRouter 후보 목록에서 자동 선택)")
    parser.add_argument("--force", action="store_true", help="이미 있는 라벨도 재생성")
    parser.add_argument("--only-gold", action="store_true", help="gold(AO 예시) 라벨만 만든다")
    parser.add_argument("--conform-only", action="store_true", help="새로 라벨링하지 않고 기존 라벨에 conform만 적용한다")
    args = parser.parse_args()

    doc_types = args.doc_type or DOC_TYPES
    if args.conform_only:
        logger.info("conform 완료: 필드 %d개 변경", conform_all(doc_types))
        return
    model = resolve_model(args.model)
    logger.info("라벨링 모델: %s (추출 모델: %s)", model, ai_settings()["model"])

    jobs = []  # (doc_type, image_path, grade, ao_path|None)
    schemas = {}
    for doc_type in doc_types:
        schemas[doc_type] = schema_for(doc_type)
        ao_json, ao_image = ao_example(doc_type)
        jobs.append((doc_type, ao_image, "gold", ao_json))
        if not args.only_gold:
            for image_path in pick_silver(doc_type, args.per_type):
                jobs.append((doc_type, image_path, "silver", None))

    started = time.monotonic()
    counts = {"ok": 0, "skip": 0, "error": 0}
    with model_override(model), ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {
            pool.submit(label_one, doc_type, image_path, schemas[doc_type], model, grade, args.force, ao_path): (doc_type, image_path, grade)
            for doc_type, image_path, grade, ao_path in jobs
        }
        for future in as_completed(futures):
            doc_type, image_path, grade = futures[future]
            status, path, exc = future.result()
            counts[status] += 1
            logger.info("%s: %s/%s (%s) -> %s", status, doc_type, image_path.name, grade, path.name)

    elapsed = time.monotonic() - started
    logger.info(
        "완료: ok=%d skip=%d error=%d, %d건 대상, %.1fs 소요, 모델=%s",
        counts["ok"], counts["skip"], counts["error"], len(jobs), elapsed, model,
    )


if __name__ == "__main__":
    main()
