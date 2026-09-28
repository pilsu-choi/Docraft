"""Natural rereads may update one leaf without moving a neighbor's evidence or row identity."""

import pytest

from backend import reprocess


def test_medical_row_identity_allows_another_amount_to_change():
    old = {"항목내역": [{"항목": "검사료", "공단부담금": "10", "본인부담금": "20"}]}
    candidate = {"항목내역": [{"항목": "검사료", "공단부담금": "30", "본인부담금": "40"}]}

    assert reprocess._candidate_path(old, candidate, "항목내역/0/공단부담금", "진료비영수증") == "30"
    assert reprocess._candidate_path(old, candidate, "항목내역/0/공단부담금", "custom") is reprocess._MISSING


def test_medical_row_identity_rejects_duplicate_or_changed_keys_and_missing_cells():
    old = {"항목내역": [{"항목": "검사료", "공단부담금": "10"}]}
    proposed = {"항목내역": [{"항목": "검사료", "공단부담금": "30"}]}
    path = "항목내역/0/공단부담금"
    assert reprocess._candidate_path(old, proposed, path, "진료비영수증") == "30"
    assert reprocess._candidate_path(old, {"항목내역": [{"항목": "검사료", "공단부담금": None}]}, path,
                                     "진료비영수증") is None
    assert reprocess._candidate_path(old, {"항목내역": [proposed["항목내역"][0]] * 2}, path,
                                     "진료비영수증") is reprocess._MISSING
    assert reprocess._candidate_path({"항목내역": old["항목내역"] * 2}, proposed, path,
                                     "진료비영수증") is reprocess._MISSING
    assert reprocess._candidate_path(old, {"항목내역": [{"항목": "입원료", "공단부담금": "30"}]}, path,
                                     "진료비영수증") is reprocess._MISSING
    assert reprocess._candidate_path(old, {"항목내역": [{"항목": "검사료"}]}, path,
                                     "진료비영수증") is reprocess._MISSING


def test_roi_grounding_only_replaces_target_and_checks_rules_on_the_same_evidence(monkeypatch):
    monkeypatch.setenv("REPROCESS_ENABLED", "true")
    monkeypatch.setenv("REPROCESS_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("REPROCESS_MAX_MODEL_CALLS", "0")
    monkeypatch.setenv("REPROCESS_MAX_MS", "10000")
    schema = {"type": "object", "properties": {"amount": {"type": "string"}, "other": {"type": "string"}}}
    original = {"type": "text", "page": 1, "text": "amount other", "bbox": [0, 0, 100, 100],
                "page_size": [100, 100]}
    roi = {**original, "roi": True}
    monkeypatch.setattr(reprocess, "_crop", lambda *args: (0, 0, 100, 100))
    monkeypatch.setattr(reprocess, "parse", lambda *args, **kwargs: ("", [roi]))
    monkeypatch.setattr(reprocess.engine, "extract", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("a verified ROI rule correction needs no model")))

    def ground(fields, _schema, blocks):
        located = any(block.get("roi") for block in blocks)
        return {"amount": {"match": "exact" if located and fields["amount"] == "new" else "none"},
                "other": {"match": "none" if located else "exact"}}

    def assess(fields, _schema, _blocks, grounds):
        return {key: {"status": "PASS" if source["match"] == "exact" else "SUSPICIOUS",
                      "issue_codes": [], "provenance": source}
                for key, source in grounds.items()}

    monkeypatch.setattr(reprocess.engine, "ground", ground)
    monkeypatch.setattr(reprocess.engine, "assess", assess)
    normalize = lambda values, blocks: {**values, "amount": "new"} if any(b.get("roi") for b in blocks) else values
    check_rules = lambda values, blocks: ([{"key": "other", "code": "roi_only"}]
                                          if any(b.get("roi") for b in blocks) else [])

    fields, grounds, quality, summary = reprocess.run(
        "scan.png", schema, [original], {"amount": "old", "other": "kept"},
        normalize=normalize, check_rules=check_rules)

    assert fields == {"amount": "new", "other": "kept"}
    assert grounds["other"]["match"] == "exact" and quality["other"]["status"] == "PASS"
    assert any(step["stage"] == "roi_parse" and step["adopted"] for step in summary["trace"])


def test_unchanged_rules_and_repeated_roi_failure_leave_budget_for_next_field(monkeypatch):
    monkeypatch.setenv("REPROCESS_ENABLED", "true")
    monkeypatch.setenv("REPROCESS_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("REPROCESS_MAX_MODEL_CALLS", "2")
    monkeypatch.setenv("REPROCESS_MAX_MS", "10000")
    schema = {"type": "object", "properties": {"first": {"type": "string"}, "second": {"type": "string"}}}
    block = {"text": "first second", "page": 1, "bbox": [0, 0, 100, 100], "page_size": [100, 100]}
    monkeypatch.setattr(reprocess, "_crop", lambda *args: (0, 0, 100, 100))
    monkeypatch.setattr(reprocess, "parse", lambda *args, **kwargs: ("", [block]))

    def quality(fields, *args):
        return ({key: {"status": "PASS" if value == "new" else "SUSPICIOUS",
                       "issue_codes": [] if value == "new" else ["no_source"],
                       "provenance": {"match": "exact"} if value == "new" else {}}
                 for key, value in fields.items()}, {})

    monkeypatch.setattr(reprocess, "_quality", quality)
    sent = []
    def extract(narrowed, *_args, on_call, **_kwargs):
        on_call()
        key = next(iter(narrowed["properties"]))
        sent.append(key)
        return {key: "new" if key == "second" else "old"}, {}
    monkeypatch.setattr(reprocess.engine, "extract", extract)

    fields, _, _, summary = reprocess.run("scan.png", schema, [block],
                                          {"first": "old", "second": "old"}, normalize=lambda values, blocks: values)

    assert fields == {"first": "old", "second": "new"}
    assert summary["attempts"] == 4 and summary["model_calls"] == 2 and sent == ["first", "second"]
    assert sum(step["stage"] == "rules" and step["reason"] == "no_change" for step in summary["trace"]) == 2
    assert any(step["reason"] == "repeated_unverified_evidence" for step in summary["trace"])
    assert not any(step["stage"] == "wide_vlm" and step["field"] == "first"
                   and step["reason"] != "repeated_unverified_evidence" for step in summary["trace"])


@pytest.mark.parametrize("conflict", [False, True])
def test_long_text_roi_change_needs_matching_full_document_read(monkeypatch, conflict):
    monkeypatch.setenv("REPROCESS_ENABLED", "true")
    monkeypatch.setenv("REPROCESS_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("REPROCESS_MAX_MODEL_CALLS", "2")
    key = "약국정보(주소)"
    old = "예시시 기존로 10 건물명 4층 401호"
    roi_value = "예시시 다른로 10 건물명 4층 401호"
    wide_value = "예시시 다른로 10" if conflict else roi_value
    schema = {"title": "약제비영수증", "type": "object", "properties": {key: {"type": "string"}}}
    block = {"page": 1, "page_size": [100, 100], "bbox": [0, 0, 100, 100], "text": key,
             "lines": [{"text": key, "bbox": [0, 0, 50, 10]}]}
    monkeypatch.setattr(reprocess, "_crop", lambda *args: (0, 0, 100, 100))
    monkeypatch.setattr(reprocess, "parse", lambda *args, **kwargs: ("", [block]))
    def ground(fields, *_args):
        value = fields[key]
        return {key: {"match": "exact" if value != old else "approximate", "page": 1,
                      "page_size": [100, 100], "bbox": [0, 0, 50, 10], "source_text": value}}
    def assess(fields, _schema, _blocks, grounds):
        return {key: {"status": "PASS" if fields[key] != old else "SUSPICIOUS", "issue_codes": [],
                      "provenance": grounds[key]}}
    monkeypatch.setattr(reprocess.engine, "ground", ground)
    monkeypatch.setattr(reprocess.engine, "assess", assess)
    calls = []
    def extract(_schema, *_args, on_call, **_kwargs):
        on_call()
        calls.append(_args[0])
        return {key: roi_value if len(calls) == 1 else wide_value}, {}
    monkeypatch.setattr(reprocess.engine, "extract", extract)
    fields, _, _, summary = reprocess.run("scan.png", schema, [block], {key: old})
    assert fields[key] == (old if conflict else roi_value) and len(calls) == 2
    assert calls[1] == []  # the confirmation reads image pixels without reusing the first OCR/candidate text
    assert any(step["reason"] == "await_wide_confirmation" for step in summary["trace"])
    assert any(step["reason"] == "conflicting_text_reads" for step in summary["trace"]) == conflict


@pytest.mark.parametrize("key,blind", [("환자성명", True), ("진료비내역-총액", False)])
def test_wide_read_of_short_text_is_blind_to_initial_ocr(monkeypatch, key, blind):
    monkeypatch.setenv("REPROCESS_ENABLED", "true")
    monkeypatch.setenv("REPROCESS_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("REPROCESS_MAX_MODEL_CALLS", "1")
    schema = {"title": "약제비영수증", "type": "object", "properties": {key: {"type": "string"}}}
    blocks = [{"page": 1, "bbox": [0, 0, 100, 100], "page_size": [100, 100], "text": key}]
    monkeypatch.setattr(reprocess, "_crop", lambda *args: None)
    monkeypatch.setattr(reprocess.engine, "ground", lambda fields, *_args: {
        key: {"match": "exact" if fields[key] == "new" else "none", "label": key}})
    monkeypatch.setattr(reprocess.engine, "assess", lambda fields, _schema, _blocks, grounds: {
        key: {"status": "PASS" if fields[key] == "new" else "SUSPICIOUS", "issue_codes": [],
              "provenance": grounds[key]}})
    sent = []
    def extract(_schema, source_blocks, *, on_call, **_kwargs):
        sent.append(source_blocks)
        on_call()
        return {key: "new"}, {}
    monkeypatch.setattr(reprocess.engine, "extract", extract)
    reprocess.run("scan.png", schema, blocks, {key: "old"})
    assert sent == [([] if blind else blocks)]


def test_immediately_proven_scalar_precedes_unresolved_fields(monkeypatch):
    monkeypatch.setenv("REPROCESS_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("REPROCESS_MAX_MODEL_CALLS", "0")
    first, second = "진료비내역-총액", "진료비내역-공단부담액"
    proof = {"match": "blank", "label": second, "evidence_type": "table_blank", "verified": True}
    monkeypatch.setattr(reprocess.typed_evidence, "blank_candidate",
                        lambda doc_type, key, value, blocks: (None, proof) if key == second else None)
    monkeypatch.setattr(reprocess, "_typed", lambda source, value: source is proof and value is None)
    def quality(fields, schema, blocks, grounds=None):
        sources = grounds if grounds is not None else {first: {}, second: {}}
        return ({key: {"status": "PASS" if key == second and fields[key] is None else "SUSPICIOUS",
                       "issue_codes": [], "provenance": sources.get(key, {})}
                 for key in fields}, sources)
    monkeypatch.setattr(reprocess, "_quality", quality)
    schema = {"title": "약제비영수증", "type": "object",
              "properties": {first: {"type": "string"}, second: {"type": ["string", "null"]}}}
    fields, _, _, summary = reprocess.run("scan.png", schema, [], {first: "95", second: "10"},
                                          normalize=lambda values, blocks: values)
    assert [step["field"] for step in summary["trace"] if step["stage"] == "select"][0] == second
    assert fields[second] is None
