"""The sum inference must never manufacture evidence for an unrelated amount."""

from backend import doctypes
from backend import inference, reprocess, rules


TOTAL = "진료비내역-총액"
PARTS = rules.FIELD_SUMS[TOTAL]


def _proof(value):
    return {"verified": True, "evidence_type": "labelled_amount", "normalized_value": value,
            "match": "typed", "page": 1, "page_size": [100, 100], "bbox": [2, 2, 8, 8],
            "source_text": value, "label": "printed"}


def test_atomic_sum_uses_all_direct_terms(monkeypatch):
    values = dict(zip(PARTS, ("50", "50", "0")))
    monkeypatch.setattr(inference.typed_evidence, "amount_candidates",
                        lambda key, blocks: (values[key], _proof(values[key])) if key in values else None)
    monkeypatch.setattr(inference.typed_evidence, "valid", lambda proof, value: proof.get("verified") is True)
    fields = {TOTAL: "95", PARTS[0]: "40", PARTS[1]: "50", PARTS[2]: "0", "other": "untouched"}
    candidate, proofs = inference.sum_group(fields, PARTS[0], [])
    assert candidate == {**fields, TOTAL: "100", PARTS[0]: "50"}
    assert proofs[TOTAL]["evidence_type"] == "derived_sum"
    assert [term["path"] for term in proofs[TOTAL]["terms"]] == list(PARTS)
    assert fields[TOTAL] == "95"


def test_sum_rejects_missing_or_unverified_term(monkeypatch):
    values = dict(zip(PARTS, ("50", "50", "0")))
    fields = {TOTAL: "95", **values}
    monkeypatch.setattr(inference.typed_evidence, "amount_candidates",
                        lambda key, blocks: None if key == PARTS[1] else (values[key], _proof(values[key])) if key in values else None)
    monkeypatch.setattr(inference.typed_evidence, "valid", lambda proof, value: proof.get("verified") is True)
    assert inference.sum_group(fields, TOTAL, []) is None
    monkeypatch.setattr(inference.typed_evidence, "amount_candidates",
                        lambda key, blocks: (values[key], {**_proof(values[key]), "verified": False}) if key in values else None)
    assert inference.sum_group(fields, TOTAL, []) is None


def test_sum_rejects_conflicting_printed_total(monkeypatch):
    values = {TOTAL: "90", **dict(zip(PARTS, ("50", "50", "0")))}
    monkeypatch.setattr(inference.typed_evidence, "amount_candidates",
                        lambda key, blocks: (values[key], _proof(values[key])) if key in values else None)
    monkeypatch.setattr(inference.typed_evidence, "valid", lambda proof, value: True)
    assert inference.sum_group(values, PARTS[0], []) is None
    monkeypatch.setattr(inference, "_aligned_amounts",
                        lambda *args: {TOTAL: ("90", _proof("90")),
                                       **{key: (value, _proof(value)) for key, value in values.items() if key != TOTAL}})
    monkeypatch.setattr(inference.typed_evidence, "amount_candidates", lambda *args: None)
    assert inference.sum_group(values, PARTS[0], [], "약제비영수증") is None


def test_rotation_requires_dominant_vertical_boxes_and_maps_back():
    vertical = [{"bbox": [10, index * 5, 13, index * 5 + 20]} for index in range(16)]
    horizontal = [{"bbox": [10, index * 5, 40, index * 5 + 5]} for index in range(16)]
    assert reprocess._vertical_ocr([{"lines": vertical}])
    assert not reprocess._vertical_ocr([{"lines": horizontal}])
    assert not reprocess._vertical_ocr([{"lines": vertical[:14]}])
    # 원본 100x80 페이지를 반시계 90도 돌린 80x100 페이지에서 읽은 좌표를 원본 좌표로 되돌린다.
    blocks = [{"bbox": [20, 40, 30, 50], "page_size": [80, 100], "lines": [{"bbox": [20, 40, 30, 50]}]}]
    mapped = reprocess.unturn(blocks, 90)
    assert mapped[0]["bbox"] == [50, 20, 60, 30] and mapped[0]["page_size"] == [100, 80]
    assert mapped[0]["lines"][0]["bbox"] == [50, 20, 60, 30]
    assert blocks[0]["bbox"] == [20, 40, 30, 50]
    cell = {"bbox": [20, 40, 30, 50], "polygon": [[20, 40], [30, 40], [30, 50], [20, 50]], "page_size": [80, 100],
            "rotation_degrees": 1.0, "blank": True, "verified": True}
    rotated = reprocess.unturn([{"page_size": [80, 100], "cells": [cell]}], 90)[0]["cells"][0]
    assert rotated["bbox"] == [50, 20, 60, 30]
    assert rotated["polygon"][0] == [60, 20]
    # 90도 단위 회전은 기울기 보정 각도와 교환되므로 빈칸 근거는 그대로 유효하다.
    assert rotated["verified"] is True and rotated["blank"] is True and rotated["page_size"] == [100, 80]
    roi = reprocess._remap([{"page_size": [100, 80], "cells": [cell]}], 1, [100, 80],
                           (10, 20, 40, 40))[0]["cells"][0]
    assert roi["polygon"][0] == [18, 40] and roi["bbox"] == [18, 40, 22, 45]


def _form_lines(second_shift=-10, duplicate=False):
    def line(text, x, y, width=45):
        return {"text": text, "bbox": [x, y, x + width, y + 10]}
    lines = [line("조제일자", 0, 20), line("2024-01-02", 60, 10),
             line("발행일", 0, 120), line("2024-01-02", 60, 120 + second_shift),
             line("본인부담금", 0, 50), line("50", 60, 40),
             line("보험자부담금", 0, 70), line("50", 60, 60),
             line("비급여전액본인", 0, 90), line("0", 60, 80)]
    if duplicate:
        lines.append(line("50", 75, 40))
    return [{"page": 1, "page_size": [200, 200], "lines": lines}]


def test_form_alignment_needs_two_independent_dates_and_unique_amounts(monkeypatch):
    monkeypatch.setattr(inference.typed_evidence, "valid", lambda proof, value: True)
    keys = (TOTAL, *PARTS)
    found = inference._aligned_amounts(keys, _form_lines(), "약제비영수증")
    assert set(found) == set(PARTS)
    assert all(proof["evidence_type"] == "aligned_amount" and len(proof["alignment_anchors"]) == 2
               for _, proof in found.values())
    assert inference._aligned_amounts(keys, _form_lines(second_shift=-3), "약제비영수증") == {}
    assert PARTS[0] not in inference._aligned_amounts(keys, _form_lines(duplicate=True), "약제비영수증")


def test_reprocess_adopts_whole_proven_sum_without_model_calls(monkeypatch):
    monkeypatch.setenv("REPROCESS_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("REPROCESS_MAX_MODEL_CALLS", "0")
    monkeypatch.setattr(reprocess, "_vertical_ocr", lambda blocks: True)
    monkeypatch.setattr(reprocess, "_rotated", lambda *args: None)
    monkeypatch.setattr(reprocess, "unturn", lambda blocks, *args: blocks)
    monkeypatch.setattr(reprocess, "parse", lambda *args, **kwargs: ("", _form_lines()))
    fields = {TOTAL: "95", PARTS[0]: "40", PARTS[1]: "50", PARTS[2]: "0"}
    schema = doctypes.schema("약제비영수증")
    schema["properties"] = {key: schema["properties"][key] for key in fields}
    schema["required"] = list(fields)
    check = lambda values, blocks: ([{"key": TOTAL, "code": "sum_mismatch"}]
                                   if int(values[TOTAL]) != sum(int(values[key]) for key in PARTS) else [])
    result, grounds, quality, summary = reprocess.run(
        "scan.png", schema, [], fields, normalize=lambda values, blocks: values, check_rules=check)
    assert result[TOTAL] == "100" and result[PARTS[0]] == "50"
    assert quality[TOTAL]["status"] == quality[PARTS[0]]["status"] == "CORRECTED"
    assert grounds[TOTAL]["evidence_type"] == "derived_sum"
    assert summary["model_calls"] == 0
    assert sum(step["adopted"] for step in summary["trace"]) == 2
