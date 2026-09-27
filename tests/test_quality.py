"""Mutated evidence must be reported before a value is automatically trusted."""

import httpx
import pytest

from backend import engine, parsers


SCHEMA = {"type": "object", "properties": {"진단일": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}}}


def block(text, page=1, bbox=None):
    return {"type": "text", "text": text, "page": page, "bbox": bbox or [0, 0, 100, 20]}


def test_grounding_preserves_ocr_text_and_flags_single_character_mutation():
    blocks = [block("진단일 2026-09-0I")]
    result = {"진단일": "2026-09-01"}
    evidence = engine._grounding_tree(result, [(item, engine._block_rows(item)) for item in blocks], SCHEMA)
    leaf = evidence["진단일"]
    assert leaf["source_text"] == "진단일 2026-09-0I"
    quality = engine.assess(result, SCHEMA, blocks, evidence)["진단일"]
    assert quality["status"] == "SUSPICIOUS"
    assert quality["action"] == "RECHECK"
    assert "approximate_source" in quality["issue_codes"]


def test_missing_and_duplicate_evidence_require_review():
    schema = {"type": "object", "properties": {"금액": {"type": "string"}}}
    absent = engine.assess({"금액": "9000"}, schema, [block("수납 8000")])["금액"]
    assert absent["status"] == "SUSPICIOUS" and "no_source" in absent["issue_codes"]
    repeated = engine.assess({"금액": "9000"}, schema, [block("총액 9000"), block("본인부담 9000", 2)])["금액"]
    assert repeated["status"] == "SUSPICIOUS" and "ambiguous_source" in repeated["issue_codes"]


def test_wrong_table_row_and_outside_page_box_require_review():
    schema = {"type": "object", "properties": {"금액": {"type": "integer"}}}
    result = {"금액": 9000}
    evidence = {"금액": {"confidence": 0.5, "page": 1, "bbox": [10, 10, 20, 20],
                       "page_size": [100, 100], "source_text": "9,000", "row_mismatch": True}}
    quality = engine.assess(result, schema, [block("금액 9,000")], evidence)["금액"]
    assert quality["status"] == "UNRESOLVED" and quality["action"] == "REVIEW"
    assert "row_mismatch" in quality["issue_codes"]
    evidence["금액"].update(row_mismatch=False, confidence=1.0, bbox=[110, 10, 120, 20])
    quality = engine.assess(result, schema, [block("금액 9,000")], evidence)["금액"]
    assert "invalid_geometry" in quality["issue_codes"] and quality["action"] == "REVIEW"


def test_missing_required_field_and_short_array_survive_grounding_serialization():
    schema = {"type": "object", "required": ["환자명"], "properties": {
        "환자명": {"type": "string"},
        "항목": {"type": "array", "minItems": 2, "items": {"type": "string"}},
    }}
    result = {"항목": ["A"]}
    quality = engine.assess(result, schema, [block("항목 A B")])
    assert quality["환자명"]["status"] == "UNRESOLVED"
    assert quality["환자명"]["issue_codes"] == ["required"]
    assert quality["항목"]["issue_codes"] == ["minItems"]
    evidence = {"항목": {"0": {"confidence": 1, "page": 1, "bbox": [0, 0, 20, 20], "source_text": "A"}}}
    engine.annotate_groundings(evidence, quality)
    assert evidence["환자명"]["status"] == "UNRESOLVED"
    assert evidence["환자명"]["source_text"] is None


def test_present_value_without_ocr_match_keeps_quality_on_grounding():
    schema = {"type": "object", "properties": {"금액": {"type": "string"}}}
    result = {"금액": "9000"}
    evidence = engine._grounding_tree(result, [(block("8000"), [["8000"]])], schema)
    engine.annotate_groundings(evidence, engine.assess(result, schema, [block("8000")], evidence))
    assert evidence["금액"]["status"] == "SUSPICIOUS"
    assert "no_source" in evidence["금액"]["issue_codes"]


def test_empty_optional_value_is_not_mislabeled_as_failed_evidence():
    assert engine.assess({"진단일": None}, SCHEMA, [block("진단일 미기재")])["진단일"]["status"] == "UNRESOLVED"
    nullable = {"type": "object", "properties": {"진단일": {"type": ["string", "null"]}}}
    assert engine.assess({"진단일": None}, nullable, [block("진단일 미기재")])["진단일"]["status"] == "PASS"


def test_missing_value_with_a_printed_key_is_rechecked():
    nullable = {"type": "object", "properties": {"진단일": {"type": ["string", "null"]}}}
    row = engine.assess({"진단일": None}, nullable, [block("진단일 2026-09-01")])["진단일"]
    assert row["status"] == "SUSPICIOUS" and "missing_value" in row["issue_codes"]


def test_value_far_from_its_own_label_is_not_confirmed_by_text_match_alone():
    value_block = block("2026-09-01", bbox=[80, 200, 180, 220])
    value_block["lines"] = [{"text": "2026-09-01", "bbox": [80, 200, 180, 220]}]
    label_block = block("진단일", bbox=[0, 0, 70, 20])
    label_block["lines"] = [{"text": "진단일", "bbox": [0, 0, 70, 20]}]
    result = {"진단일": "2026-09-01"}
    row = engine.assess(result, SCHEMA, [label_block, value_block])["진단일"]
    assert row["status"] == "SUSPICIOUS" and "distant_label" in row["issue_codes"]


def test_incomplete_remote_page_response_fails_instead_of_silently_shifting_pages(monkeypatch, tmp_path):
    source = tmp_path / "scan.png"
    source.write_bytes(b"synthetic")
    monkeypatch.setenv("PADDLEOCR_BASE_URL", "https://ocr.example")
    reply = {"result": {"layoutParsingResults": [{"markdown": {"text": "first"}}]}}
    monkeypatch.setattr(parsers.httpx, "post", lambda url, **_: httpx.Response(200, json=reply, request=httpx.Request("POST", url)))
    with pytest.raises(parsers.ParseError, match="2페이지 중 1페이지"):
        parsers._remote_paddle(source, 0, expected_pages=2)
