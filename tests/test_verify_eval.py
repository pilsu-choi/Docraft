"""평가 스크립트의 단계 의존성과 집계 계약."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from backend import rules


SCRIPT = Path(__file__).parents[1] / "scripts" / "verify_eval.py"
spec = importlib.util.spec_from_file_location("verify_eval_test", SCRIPT)
verify_eval = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(verify_eval)
import verify_label


def test_rules_stage_extracts_raw_even_when_raw_is_not_requested(monkeypatch, tmp_path):
    item = SimpleNamespace(image_path=tmp_path / "scan.png", doc_type="진단서", ao_path=None)
    item.image_path.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(verify_eval, "cached_parse", lambda *args: ("", [{"text": "x"}]))
    monkeypatch.setattr(verify_eval, "cached_extract", lambda *args: calls.append("extract") or {"진단일": "20230228"})
    monkeypatch.setattr(rules, "apply", lambda doc_type, raw, blocks: {**raw, "rule": "done"})

    preds, errors = verify_eval.run_stages(item, {}, ("rules",), False)

    assert calls == ["extract"]
    assert preds["rules"]["rule"] == "done"
    assert errors == {}


def test_ao_stage_accepts_a_real_ao_path_for_silver_item(tmp_path):
    ao = tmp_path / "ao.json"
    ao.write_text(json.dumps({"documents": [{"extracted_fields": [{"key": "진단일", "value": "20230228"}]}]}), encoding="utf-8")
    item = SimpleNamespace(image_path=tmp_path / "scan.png", doc_type="진단서", grade="silver", ao_path=str(ao))

    preds, errors = verify_eval.run_stages(item, {}, ("ao",), False)

    assert preds["ao"] == {"진단일": "20230228"}
    assert errors == {}


def test_summary_reports_skip_error_and_strict_normalized_score():
    rows = [("병명", "이상체중감소", "(주상병)이상체중감소", "text")]
    stat = verify_eval.aggregate(rows)
    assert stat["correct"] == 1  # legacy loose text comparison
    assert stat["strict_correct"] == 0
    entries = [
        {"doc_type": "진단서", "stages": {"rules": {**stat, "rows": rows}}},
        {"doc_type": "진단서", "stages": {"rules": {"correct": 0, "total": 0, "fp": 0, "strict_correct": 0,
                                                       "strict_total": 0, "strict_fp": 0, "rows": [], "error": "AO 결과 없음"}}},
    ]

    summary, _ = verify_eval.build_summaries(entries, ["진단서"], ("rules",))

    assert summary["진단서"]["rules"] == {"correct": 1, "total": 1, "fp": 0, "strict_correct": 0,
                                            "strict_total": 1, "strict_fp": 0, "evaluated": 1, "skipped": 1, "error": 0}


def test_strict_fp_counts_null_to_zero_that_legacy_rules_accepts():
    stat = verify_eval.aggregate([("금액", None, "0", "amount")])

    assert stat["fp"] == 0
    assert stat["strict_fp"] == 1

    stat = verify_eval.aggregate([("텍스트", None, "값", "text")])
    assert stat["fp"] == 1
    assert stat["strict_fp"] == 1


def test_manifest_deduplicates_candidate_content_and_preserves_existing(tmp_path, monkeypatch):
    samples = tmp_path / "files" / "진단서_samples"
    samples.mkdir(parents=True)
    labels = tmp_path / "labels" / "진단서"
    labels.mkdir(parents=True)
    for name, content in (("original", b"existing"), ("copy", b"existing"),
                          ("new1", b"new"), ("new2", b"new"), ("new3", b"different")):
        (samples / f"{name}.png").write_bytes(content)
    label = {"image": str(samples / "original.png"), "doc_type": "진단서", "grade": "silver"}
    (labels / "original.json").write_text(json.dumps(label))
    monkeypatch.setattr(verify_label, "LABELS_ROOT", labels.parent)
    monkeypatch.setattr(verify_label, "DATA_ROOT", samples.parent)
    monkeypatch.setattr(verify_label, "DOC_TYPES", ["진단서"])

    manifest = verify_label.build_manifest(tmp_path / "manifest.json", holdout_per_type=2)

    assert len(manifest["items"]) == 3
    assert len({item["content_sha256"] for item in manifest["items"]}) == 3
    assert sum(item["split"] == "existing" for item in manifest["items"]) == 1
