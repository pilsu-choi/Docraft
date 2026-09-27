"""Create paired image perturbations and evaluate them with verify_eval.py."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageSequence


VARIANTS = ("rotate", "blur", "occlude")
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT.parents[1] / "data/verify/accuracy-20260922/manifest.json"
CODE_FILES = ("backend/engine.py", "backend/parsers.py", "backend/rules.py", "scripts/verify_eval.py")


def make_variant(source: Path, target: Path, name: str) -> dict:
    """Save a transformed copy, preserving every raster page and leaving the source untouched."""
    with Image.open(source) as image:
        frames = [ImageOps.exif_transpose(frame.copy()).convert("RGB") for frame in ImageSequence.Iterator(image)]
    if not frames:
        raise ValueError(f"이미지 프레임이 없습니다: {source.suffix}")

    parameters = []

    def transform(frame: Image.Image, page: int) -> Image.Image:
        width, height = frame.size
        if name == "rotate":
            parameters.append({"page": page, "width": width, "height": height, "degrees": 2, "expand": True})
            return frame.rotate(2, resample=Image.Resampling.BICUBIC, expand=True, fillcolor="white")
        if name == "blur":
            parameters.append({"page": page, "width": width, "height": height, "radius": 0.8})
            return frame.filter(ImageFilter.GaussianBlur(radius=0.8))
        if name == "occlude":
            draw = ImageDraw.Draw(frame)
            x1, x2 = round(width * 0.43), round(width * 0.57)
            y1, y2 = round(height * 0.47), round(height * 0.55)
            draw.rectangle((x1, y1, x2, y2), fill=(96, 96, 96))
            parameters.append({"page": page, "width": width, "height": height,
                               "box_pixels": [x1, y1, x2, y2], "fill_rgb": [96, 96, 96]})
            return frame
        raise ValueError(f"지원하지 않는 변형: {name}")

    transformed = [transform(frame, index + 1) for index, frame in enumerate(frames)]
    target.parent.mkdir(parents=True, exist_ok=True)
    transformed[0].save(target, format="TIFF", save_all=True, append_images=transformed[1:])
    return {"kind": name, "pages": parameters}


def counts(entries: list[dict], stage: str) -> dict:
    fields = ("correct", "total", "fp", "strict_correct", "strict_total", "strict_fp")
    return {key: sum((item.get("stages", {}).get(stage) or {}).get(key, 0) for item in entries) for key in fields}


def code_fingerprint() -> dict:
    files = {name: hashlib.sha256((REPO_ROOT / name).read_bytes()).hexdigest() for name in CODE_FILES}
    digest = hashlib.sha256("".join(files[name] for name in CODE_FILES).encode()).hexdigest()
    return {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip(),
            "source_sha256": digest, "files": files}


def quality_counts(entries: list[dict], item_by_image: dict[str, dict], cache_root: Path) -> dict:
    """Reassess cached raw extraction against cached OCR blocks without another model call."""
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from backend import engine
    from verify_label import schema_for

    result = {"documents": 0, "fields": 0, "status": {}, "action": {}, "issue_codes": {}}
    for entry in entries:
        item = item_by_image[entry["image"]]
        doc_type = item["doc_type"]
        stem = Path(item["image"]).stem
        parse_path = cache_root / f"{doc_type}__{stem}.parse.json"
        extract_path = cache_root / f"{doc_type}__{stem}.extract.json"
        if not parse_path.is_file() or not extract_path.is_file():
            continue
        blocks = json.loads(parse_path.read_text(encoding="utf-8"))["blocks"]
        extracted = json.loads(extract_path.read_text(encoding="utf-8"))["result"]
        assessed = engine.assess(extracted, schema_for(doc_type), blocks)
        result["documents"] += 1
        for field in assessed.values():
            result["fields"] += 1
            for key, value in (("status", field["status"]), ("action", field["action"])):
                result[key][value] = result[key].get(value, 0) + 1
            for code in field["issue_codes"]:
                result["issue_codes"][code] = result["issue_codes"].get(code, 0) + 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-root", type=Path, default=Path("/tmp/parse-extract-quality/perturbation"))
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    source_manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    gold = [item for item in source_manifest["items"] if item.get("grade") == "gold"]
    if len(gold) != 4:
        parser.error(f"기존 gold 문서 4건이 필요합니다: {len(gold)}건")

    out = args.output_root.resolve()
    label_root, image_root = out / "labels", out / "images"
    items, variant_docs, parameters = [], {name: [] for name in ("original", *VARIANTS)}, {}
    for index, item in enumerate(gold, 1):
        source_label = Path(item["label"])
        label = json.loads(source_label.read_text(encoding="utf-8"))
        original_image = Path(item["image"]).resolve()
        original_alias = image_root / f"case-{index:02d}-original{original_image.suffix.lower()}"
        original_alias.parent.mkdir(parents=True, exist_ok=True)
        original_alias.symlink_to(original_image)
        original_label_path = label_root / item["doc_type"] / f"case-{index:02d}-original.json"
        original_label_path.parent.mkdir(parents=True, exist_ok=True)
        original_label_path.write_text(json.dumps({**label, "image": str(original_alias)}, ensure_ascii=False), encoding="utf-8")
        original_item = {key: value for key, value in item.items() if key not in {"label", "content_sha256"}}
        original_item.update(image=str(original_alias), label=str(original_label_path), variant="original",
                             transform={"kind": "identity"})
        items.append(original_item)
        variant_docs["original"].append(original_item)
        for variant in VARIANTS:
            image = image_root / f"case-{index:02d}-{variant}.tif"
            parameters[image.name] = make_variant(original_image, image, variant)
            label_path = label_root / item["doc_type"] / f"case-{index:02d}-{variant}.json"
            label_path.parent.mkdir(parents=True, exist_ok=True)
            label_path.write_text(json.dumps({**label, "image": str(image)}, ensure_ascii=False), encoding="utf-8")
            variant_item = {key: value for key, value in item.items() if key not in {"image", "label", "content_sha256"}}
            variant_item.update(image=str(image), split=variant, label=str(label_path), variant=variant,
                                transform=parameters[image.name])
            items.append(variant_item)
            variant_docs[variant].append(variant_item)

    manifest = {"version": 1, "created_at": source_manifest.get("created_at"),
                "selection": "four existing gold documents; original plus paired 2 degree rotation, Gaussian blur, and centered occlusion",
                "label_root": str(label_root), "items": items}
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    before = set((REPO_ROOT / "data/verify").glob("eval-*.json"))
    cache_root = out / "cache"
    command = [sys.executable, str(REPO_ROOT / "scripts/verify_eval.py"), "--manifest", str(manifest_path),
               "--grade", "gold", "--stage", "raw", "--stage", "rules", "--workers", str(args.workers),
               "--cache-root", str(cache_root)]
    fingerprint_before = code_fingerprint()
    started = time.monotonic()
    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    elapsed = round(time.monotonic() - started, 1)
    (out / "verify_eval.log").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    generated = sorted(set((REPO_ROOT / "data/verify").glob("eval-*.json")) - before,
                       key=lambda path: path.stat().st_mtime)
    if result.returncode or not generated:
        print(json.dumps({"exit": result.returncode, "elapsed_seconds": elapsed,
                          "error": "verify_eval_failed", "log": str(out / "verify_eval.log")}, ensure_ascii=False))
        return result.returncode or 1

    evaluation = json.loads(generated[-1].read_text(encoding="utf-8"))
    item_by_image = {Path(item["image"]).name: item for item in items}
    results, quality = {}, {}
    for variant, docs in variant_docs.items():
        names = {Path(item["image"]).name for item in docs}
        entries = [item for item in evaluation["items"] if item["image"] in names]
        results[variant] = {stage: counts(entries, stage) for stage in ("raw", "rules")}
        quality[variant] = quality_counts(entries, item_by_image, cache_root)
    base_flags = quality["original"]["status"].get("SUSPICIOUS", 0) + quality["original"]["status"].get("UNRESOLVED", 0)
    for variant in VARIANTS:
        flags = quality[variant]["status"].get("SUSPICIOUS", 0) + quality[variant]["status"].get("UNRESOLVED", 0)
        quality[variant]["suspicious_or_unresolved_delta_vs_original"] = flags - base_flags
    fingerprint_after = code_fingerprint()
    report = {"source": "four existing gold documents; OCR/model output is not promoted to gold",
              "elapsed_seconds": elapsed, "documents_per_variant": len(gold),
              "occlusion_note": "fixed centered region; visibility was not adjudicated per field, so detection recall and occlusion accuracy are not claimed",
              "code_before": fingerprint_before, "code_after": fingerprint_after,
              "code_unchanged_during_run": fingerprint_before["source_sha256"] == fingerprint_after["source_sha256"],
              "results": results, "quality_from_cached_parse_extract": quality,
              "cache_root": str(cache_root), "manifest": str(manifest_path)}
    report_path = out / "summary.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"exit": 0, "elapsed_seconds": elapsed, "report": str(report_path),
                      "results": results, "quality": quality,
                      "code_head": report["code_after"]["head"],
                      "source_sha256": report["code_after"]["source_sha256"],
                      "code_unchanged_during_run": report["code_unchanged_during_run"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
