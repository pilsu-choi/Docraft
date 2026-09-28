"""Typed OCR evidence must preserve printed tokens and field roles."""

from backend import doctypes, engine, reprocess


def block(text, bbox=None):
    bbox = bbox or [10, 10, 180, 30]
    return {"text": text, "page": 1, "bbox": bbox, "page_size": [200, 100],
            "lines": [{"text": text, "bbox": bbox}]}


def test_labelled_korean_date_is_typed_and_keeps_printed_token():
    schema = doctypes.schema("진단서")
    fields = {"진단일": "20260927"}
    blocks = [block("진단연월일: 2026년 9월 27일")]
    source = engine.ground(fields, schema, blocks)["진단일"]

    assert source["match"] == "typed" and source["evidence_type"] == "date_equivalent"
    assert source["source_text"] == "2026년 9월 27일" and source["bbox"] == [10, 10, 180, 30]
    assert engine.assess(fields, schema, blocks, {"진단일": source})["진단일"]["status"] == "PASS"


def test_range_roles_do_not_swap_or_infer_unlabelled_accident_date():
    schema = doctypes.schema("진료비영수증")
    blocks = [block("진료기간: 2026.09.01 ~ 2026.09.27")]
    fields = {"환자정보-진료시작일": "20260901", "환자정보-진료종료일": "20260927",
              "사고발생일자": "20260901"}
    grounded = engine.ground(fields, schema, blocks)

    assert grounded["환자정보-진료시작일"]["role"] == "start"
    assert grounded["환자정보-진료종료일"]["role"] == "end"
    assert grounded["환자정보-진료시작일"]["source_text"] == "2026.09.01"
    assert grounded["환자정보-진료종료일"]["source_text"] == "2026.09.27"
    assert grounded["사고발생일자"].get("match") != "typed"


def test_explicit_checkbox_mark_can_ground_y_or_n_but_absence_cannot():
    schema = doctypes.schema("진단서")
    fields = {"임상적추정": "Y", "최종진단": "N"}
    blocks = [block("☑ 임상적 추정", [0, 0, 80, 20]), block("□ 최종진단", [0, 25, 80, 45])]
    grounded = engine.ground(fields, schema, blocks)

    assert grounded["임상적추정"]["source_text"] == "☑"
    assert grounded["최종진단"]["source_text"] == "□"
    assert grounded["최종진단"]["role"] == "unchecked"
    assert engine.ground({"최종진단": "N"}, schema, [block("최종진단")])["최종진단"].get("match") != "typed"


def test_one_checkbox_between_two_labels_cannot_prove_both():
    schema = doctypes.schema("진단서")
    grounded = engine.ground({"임상적추정": "Y", "최종진단": "Y"}, schema,
                             [block("임상적추정 ☑ 최종진단")])
    assert grounded["임상적추정"].get("evidence_type") != "checkbox_mark"
    assert grounded["최종진단"].get("evidence_type") != "checkbox_mark"


def test_generic_eight_digit_identifier_is_not_treated_as_a_date():
    schema = {"title": "custom", "type": "object", "properties": {"id": {"type": "string"}}}
    grounded = engine.ground({"id": "20260927"}, schema, [block("id: 2026년 9월 27일")])
    assert grounded["id"].get("evidence_type") is None


def test_verified_empty_physical_cell_proves_null_but_not_zero():
    schema = doctypes.schema("진료비영수증")
    table = {"text": "<table></table>", "page": 1, "bbox": [0, 0, 200, 90], "page_size": [200, 100],
             "rows": [["항목", "공단부담금"], ["총계", ""]],
             "cells": [{"row": 0, "column": 1, "text": "공단부담금", "bbox": [80, 0, 180, 25], "page": 1,
                        "page_size": [200, 100], "rowspan": 1, "colspan": 1, "verified": True, "blank": False},
                       {"row": 1, "column": 1, "text": "", "bbox": [80, 25, 180, 55], "page": 1,
                        "page_size": [200, 100], "rowspan": 1, "colspan": 1, "verified": True, "blank": True}]}
    fields = {"항목내역": [{"항목": "합계", "공단부담금": None}]}
    source = engine.ground(fields, schema, [table])["항목내역"]["0"]["공단부담금"]
    assert source["match"] == "blank" and source["normalized_value"] is None
    assert source["bbox"] == [80, 25, 180, 55] and source["role"] == "total_cell"
    assert engine.ground({"항목내역": [{"항목": "합계", "공단부담금": "0"}]}, schema, [table])[
        "항목내역"]["0"]["공단부담금"].get("match") != "blank"


def test_scalar_blank_requires_adjacent_verified_cell():
    schema = doctypes.schema("진료비영수증")
    block = {"text": "<table></table>", "page": 1, "bbox": [0, 0, 180, 30], "page_size": [200, 100],
             "rows": [["상한액초과금", ""]],
             "cells": [{"row": 0, "column": 0, "text": "상한액초과금", "bbox": [0, 0, 90, 30],
                        "page": 1, "page_size": [200, 100], "rowspan": 1, "colspan": 1, "verified": True, "blank": False},
                       {"row": 0, "column": 1, "text": "", "bbox": [90, 0, 180, 30],
                        "page": 1, "page_size": [200, 100], "rowspan": 1, "colspan": 1, "verified": True, "blank": True}]}
    source = engine.ground({"상환액초과금": None}, schema, [block])["상환액초과금"]
    assert source["evidence_type"] == "table_blank" and source["source_text"] == ""
    block["cells"][1]["verified"] = False
    assert engine.ground({"상환액초과금": None}, schema, [block])["상환액초과금"].get("match") != "blank"


def test_total_scalar_uses_unique_leaf_header_and_total_cell_not_table_box():
    schema = doctypes.schema("진료비영수증")
    table = {"text": "<table></table>", "page": 1, "bbox": [0, 0, 200, 100], "page_size": [200, 100],
             "rows": [["항목", "공단부담금"], ["", ""], ["진료", "500"], ["총계", "500"]],
             "cells": [{"row": 0, "column": 1, "text": "공단부담금", "bbox": [80, 0, 180, 20],
                        "page": 1, "page_size": [200, 100], "rowspan": 1, "colspan": 1, "verified": True, "blank": False},
                       {"row": 3, "column": 1, "text": "500", "bbox": [80, 70, 180, 95],
                        "page": 1, "page_size": [200, 100], "rowspan": 1, "colspan": 1, "verified": True, "blank": False}]}
    source = engine.ground({"공단부담총액": "500"}, schema, [table])["공단부담총액"]
    assert source["evidence_type"] == "table_cell" and source["role"] == "total_cell"
    assert source["bbox"] == [80, 70, 180, 95] and source["normalized_value"] == "500"
    table["cells"][1]["verified"] = False
    assert engine.ground({"공단부담총액": "500"}, schema, [table])[
        "공단부담총액"].get("evidence_type") != "table_cell"


def test_merged_parent_and_unique_child_define_total_column():
    schema = doctypes.schema("세부내역서")
    table = {"text": "<table></table>", "page": 1, "bbox": [0, 0, 220, 100], "page_size": [220, 100],
             "rows": [["", "본인부담액", "본인부담액"], ["", "급여", "비급여"], ["총계", "700", "200"]],
             "cells": [{"row": 0, "column": 1, "text": "본인부담액", "bbox": [80, 0, 200, 25],
                        "page": 1, "page_size": [220, 100], "rowspan": 1, "colspan": 2, "verified": True, "blank": False},
                       {"row": 1, "column": 1, "text": "급여", "bbox": [80, 25, 140, 50],
                        "page": 1, "page_size": [220, 100], "rowspan": 1, "colspan": 1, "verified": True, "blank": False},
                       {"row": 1, "column": 2, "text": "비급여", "bbox": [140, 25, 200, 50],
                        "page": 1, "page_size": [220, 100], "rowspan": 1, "colspan": 1, "verified": True, "blank": False},
                       {"row": 2, "column": 1, "text": "700", "bbox": [80, 50, 140, 75],
                        "page": 1, "page_size": [220, 100], "rowspan": 1, "colspan": 1, "verified": True, "blank": False}]}
    source = engine.ground({"급여_본인부담총액": "700"}, schema, [table])["급여_본인부담총액"]
    assert source["evidence_type"] == "table_cell" and source["column"] == 1
    table["cells"][0]["colspan"] = 1
    table["cells"][1]["column"] = 2
    assert engine.ground({"급여_본인부담총액": "700"}, schema, [table])[
        "급여_본인부담총액"].get("evidence_type") != "table_cell"


def test_date_label_and_date_on_adjacent_ocr_lines_bind_to_one_field():
    schema = doctypes.schema("진단서")
    block_ = {"text": "", "page": 1, "bbox": [0, 0, 200, 90], "page_size": [200, 100],
              "lines": [{"text": "입원일", "bbox": [10, 10, 50, 30]},
                        {"text": "2026년 9월 1일", "bbox": [55, 10, 130, 30]},
                        {"text": "퇴원일", "bbox": [140, 10, 175, 30]}]}
    source = engine.ground({"입원일자": "20260901"}, schema, [block_])["입원일자"]
    assert source["geometry_scope"] == "line_group" and source["source_text"] == "2026년 9월 1일"
    assert source["bbox"] == [10, 10, 130, 30]


def test_other_date_label_stops_line_group_before_its_value():
    schema = doctypes.schema("진단서")
    block_ = {"text": "", "page": 1, "bbox": [0, 0, 200, 90], "page_size": [200, 100],
              "lines": [{"text": "진단일", "bbox": [10, 10, 40, 30]},
                        {"text": "생년월일", "bbox": [45, 10, 85, 30]},
                        {"text": "2026.09.27", "bbox": [90, 10, 160, 30]}]}
    grounded = engine.ground({"진단일": "20260927"}, schema, [block_])
    assert grounded["진단일"].get("evidence_type") != "date_equivalent"


def test_reprocess_can_replace_misread_with_proven_blank_only(monkeypatch):
    monkeypatch.setenv("REPROCESS_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("REPROCESS_MAX_MODEL_CALLS", "0")
    schema = {"title": "진료비영수증", "type": "object", "required": ["상환액초과금"],
              "properties": {"상환액초과금": {"type": ["string", "null"]}}}
    block_ = {"text": "<table><tr><td>상한액초과금</td><td></td></tr></table>",
              "page": 1, "bbox": [0, 0, 180, 30], "page_size": [200, 100],
              "rows": [["상한액초과금", ""]],
              "cells": [{"row": 0, "column": 0, "text": "상한액초과금", "bbox": [0, 0, 90, 30],
                         "page": 1, "page_size": [200, 100], "verified": True, "blank": False},
                        {"row": 0, "column": 1, "text": "", "bbox": [90, 0, 180, 30],
                         "page": 1, "page_size": [200, 100], "verified": True, "blank": True}]}
    fields, _, quality, summary = reprocess.run("scan.png", schema, [block_], {"상환액초과금": "777"},
                                                  normalize=lambda values, blocks: values)
    assert fields["상환액초과금"] is None
    assert quality["상환액초과금"]["status"] == "CORRECTED"
    assert summary["trace"][-1]["proposed"] is None and summary["trace"][-1]["adopted"]
    block_["cells"][1]["verified"] = False
    fields, _, _, summary = reprocess.run("scan.png", schema, [block_], {"상환액초과금": "777"},
                                          normalize=lambda values, blocks: values)
    assert fields["상환액초과금"] == "777" and not any(step["adopted"] for step in summary["trace"])


def test_roi_parse_new_blank_proof_can_recover_without_model_call(monkeypatch):
    monkeypatch.setenv("REPROCESS_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("REPROCESS_MAX_MODEL_CALLS", "0")
    schema = {"title": "진료비영수증", "type": "object", "required": ["상환액초과금"],
              "properties": {"상환액초과금": {"type": ["string", "null"]}}}
    original = {"text": "상한액초과금", "page": 1, "bbox": [0, 0, 100, 40], "page_size": [100, 100]}
    local = {"text": "<table><tr><td>상한액초과금</td><td></td></tr></table>",
             "page": 1, "bbox": [0, 0, 100, 40], "page_size": [100, 100],
             "rows": [["상한액초과금", ""]],
             "cells": [{"row": 0, "column": 0, "text": "상한액초과금", "bbox": [0, 0, 50, 40],
                        "page": 1, "page_size": [100, 100], "verified": True, "blank": False},
                       {"row": 0, "column": 1, "text": "", "bbox": [50, 0, 100, 40],
                        "page": 1, "page_size": [100, 100], "verified": True, "blank": True}]}
    monkeypatch.setattr(reprocess, "_crop", lambda *args: (0, 0, 100, 100))
    monkeypatch.setattr(reprocess, "parse", lambda *args, **kwargs: ("", [local]))
    fields, groundings, _, summary = reprocess.run("scan.png", schema, [original], {"상환액초과금": "777"},
                                                   normalize=lambda values, blocks: values)
    assert fields["상환액초과금"] is None and summary["extra_model_calls"] == 0
    assert any(step["stage"] == "roi_parse" and step["adopted"] for step in summary["trace"])
    assert groundings["상환액초과금"]["bbox"] == [50, 0, 100, 40]


def test_forged_typed_claim_cannot_make_missing_value_pass():
    from backend.typed_evidence import valid
    schema = doctypes.schema("진료비영수증")
    block_ = block("상한액초과금")
    fake = {"confidence": 1, "page": 1, "bbox": [10, 10, 180, 30], "page_size": [200, 100],
            "source_text": "", "match": "blank", "evidence_type": "table_blank", "transform": "blank_to_null",
            "role": "field_cell", "label": "상한액초과금", "geometry_scope": "cell", "normalized_value": None,
            "verified": True, "basis": "image_cell_blank", "field_key": "상환액초과금",
            "blank_method": "closed_cell"}
    assert valid(fake, None)
    fake["bbox"] = [10, 10, 210, 30]
    assert not valid(fake, None)
    quality = engine.assess({"상환액초과금": None}, schema, [block_], {"상환액초과금": fake})
    assert quality["상환액초과금"]["status"] != "PASS"


def test_typed_value_mismatch_is_unresolved_and_not_exposed():
    from backend import verify
    schema = doctypes.schema("진단서")
    source = engine.ground({"진단일": "20260927"}, schema, [block("진단일 2026년 9월 27일")])["진단일"]
    source["normalized_value"] = "20260926"
    quality = engine.assess({"진단일": "20260927"}, schema, [block("진단일 2026년 9월 27일")],
                            {"진단일": source})
    assert "invalid_typed_proof" in quality["진단일"]["issue_codes"]
    assert quality["진단일"]["status"] == "UNRESOLVED"
    assert verify._exposed_grounding(source, "20260927") is None


def test_payment_group_short_card_label_proves_only_its_closed_blank_cell():
    from backend import typed_evidence as typed
    cells = [
        {"row": 0, "column": 0, "rowspan": 2, "colspan": 1, "text": "납부한 금액",
         "bbox": [0, 0, 50, 60], "verified": True},
        {"row": 0, "column": 1, "rowspan": 1, "colspan": 1, "text": "카 드",
         "bbox": [50, 0, 100, 30], "verified": True},
        {"row": 0, "column": 2, "rowspan": 1, "colspan": 1, "text": "",
         "bbox": [100, 0, 170, 30], "verified": True, "blank": True},
        {"row": 1, "column": 1, "rowspan": 1, "colspan": 1, "text": "합계",
         "bbox": [50, 30, 100, 60], "verified": True},
    ]
    source = {"page": 1, "page_size": [200, 100], "cells": cells, "lines": []}
    candidate = typed.blank_candidate("진료비영수증", "납부한금액_카드", "999", [source])
    assert candidate and candidate[0] is None
    assert candidate[1]["group_label"] == "납부한 금액"
    assert typed.valid(candidate[1], None)
    assert typed.blank_candidate("진료비영수증", "납부한금액_현금", "999", [source]) is None
    cells[2]["verified"] = False
    assert typed.blank_candidate("진료비영수증", "납부한금액_카드", "999", [source]) is None


def test_rotated_blank_hull_is_valid_only_for_a_real_convex_cell():
    from backend import typed_evidence as typed
    proof = {"page": 1, "page_size": [200, 100], "bbox": [10, 10, 110, 61],
             "polygon": [[10, 10], [110, 11], [109, 61], [11, 60]], "rotation_degrees": 0.5,
             "blank_method": "deskewed_closed_cell_noise_floor_v1", "geometry_scope": "rotated_cell_hull",
             "source_text": "", "match": "blank", "evidence_type": "table_blank", "transform": "blank_to_null",
             "role": "field_cell", "label": "카드", "normalized_value": None, "verified": True,
             "field_key": "납부한금액_카드", "basis": "image_cell_blank"}
    assert typed.valid(proof, None)
    proof["polygon"] = [[10, 10], [110, 11], [11, 60], [109, 61]]
    assert not typed.valid(proof, None)


def test_narrative_date_conflict_blocks_blank_candidate():
    from backend import typed_evidence as typed
    source = {"page": 1, "page_size": [200, 100], "cells": [
        {"row": 0, "column": 0, "rowspan": 1, "colspan": 1, "text": "입원일자",
         "bbox": [0, 0, 80, 30], "verified": True},
        {"row": 0, "column": 1, "rowspan": 1, "colspan": 1, "text": "",
         "bbox": [80, 0, 180, 30], "verified": True, "blank": True}],
         "lines": [{"text": "입원 치료 2026년 9월 1일", "bbox": [0, 40, 180, 55]},
                   {"text": "퇴원 2026년 9월 5일", "bbox": [0, 60, 180, 75]}]}
    assert typed.blank_candidate("입퇴원확인서", "입원일자", "20260901", [source]) is None


def test_checkbox_inference_requires_registered_group_and_unique_mark():
    from backend import typed_evidence as typed
    selected = block("☑ 임상적추정", [0, 0, 80, 20])
    selected["lines"].append({"text": "최종진단", "bbox": [85, 0, 150, 20]})
    candidate = typed.inferred_checkbox_candidate("진단서", "최종진단", [selected])
    assert candidate and candidate[0] == "N" and typed.valid(candidate[1], "N")
    assert typed.inferred_checkbox_candidate("진료비영수증", "최종진단", [selected]) is None
    selected["lines"][1]["text"] = "☑ 최종진단"
    assert typed.inferred_checkbox_candidate("진단서", "최종진단", [selected]) is None
