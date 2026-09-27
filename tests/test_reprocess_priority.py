"""Priority is based on attributable evidence, without changing candidate acceptance."""

from backend import reprocess


BLOCK = {"text": "amount old", "page": 1, "bbox": [0, 0, 200, 100],
         "page_size": [200, 100], "lines": [{"text": "amount old", "bbox": [10, 10, 90, 25]}]}


def _item(status="UNRESOLVED", *, match="exact", bbox=None):
    return {"status": status, "issue_codes": [], "provenance": {
        "page": 1, "bbox": bbox or [10, 10, 90, 25], "page_size": [200, 100],
        "source_text": "amount old", "match": match}}


def _setup(monkeypatch, attempts=1):
    monkeypatch.setenv("REPROCESS_ENABLED", "true")
    monkeypatch.setenv("REPROCESS_MAX_ATTEMPTS", str(attempts))
    monkeypatch.setenv("REPROCESS_MAX_MODEL_CALLS", "1")
    monkeypatch.setattr(reprocess, "_crop", lambda *args: None)
    def extract(*args, **kwargs):
        kwargs["on_call"]()
        return {"amount": "new"}, {}
    monkeypatch.setattr(reprocess.engine, "extract", extract)


def test_later_located_rule_target_precedes_unlocated_and_preserves_other(monkeypatch):
    _setup(monkeypatch)
    schema = {"properties": {"missing": {}, "amount": {"title": "amount"}}}
    fields = {"missing": "kept", "amount": "old"}
    def quality(values, *args):
        return {"missing": {"status": "UNRESOLVED", "issue_codes": ["no_source"], "provenance": {}},
                "amount": _item()}, {}
    monkeypatch.setattr(reprocess, "_quality", quality)
    rule = lambda values, blocks: [{"key": "amount", "code": "bad_date", "rule": "DATE"}]
    result, _, _, summary = reprocess.run("scan.png", schema, [BLOCK], fields, check_rules=rule)
    assert summary["trace"][0]["field"] == "amount"
    assert summary["trace"][0]["reason"] == "located_rule_violation"
    assert summary["attempts"] == 1 and summary["extra_model_calls"] == 1
    assert result["missing"] == "kept" and result["amount"] == "old"


def test_direct_rule_on_pass_requires_actual_rule_resolution(monkeypatch):
    _setup(monkeypatch)
    schema = {"properties": {"amount": {"title": "amount"}}}
    monkeypatch.setattr(reprocess, "_quality", lambda values, *args: ({"amount": _item("PASS")}, {}))
    persistent = lambda values, blocks: [{"key": "amount", "code": "sum_mismatch", "rule": "SUM"}]
    fields, _, quality, summary = reprocess.run("scan.png", schema, [BLOCK], {"amount": "old"}, check_rules=persistent)
    assert fields["amount"] == "old" and quality["amount"]["status"] == "SUSPICIOUS"
    assert summary["trace"][0]["reason"] == "located_rule_violation"
    assert not any(step["adopted"] for step in summary["trace"])

    clears = lambda values, blocks: persistent(values, blocks) if values["amount"] == "old" else []
    fields, _, quality, summary = reprocess.run("scan.png", schema, [BLOCK], {"amount": "old"}, check_rules=clears)
    assert fields["amount"] == "new" and quality["amount"]["status"] == "CORRECTED"
    assert any(step["adopted"] for step in summary["trace"])


def test_exact_line_outweighs_block_box_and_approximate_line(monkeypatch):
    _setup(monkeypatch)
    schema = {"properties": {key: {} for key in ("block", "approx", "line")}}
    fields = {"block": "a", "approx": "b", "line": "c"}
    def quality(*args):
        return {"block": _item(bbox=BLOCK["bbox"]), "approx": _item(match="approximate"),
                "line": _item()}, {}
    monkeypatch.setattr(reprocess, "_quality", quality)
    _, _, _, summary = reprocess.run("scan.png", schema, [BLOCK], fields)
    assert summary["trace"][0]["field"] == "line"
    assert summary["trace"][0]["reason"] == "located_source"


def test_row_and_table_flags_rank_only_existing_review_leaves():
    fields = {"items": [{"amount": "1"}, {"amount": "2", "name": "x"}]}
    quality = {"items/0/amount": _item(), "items/1/amount": _item(), "items/1/name": _item("PASS")}
    flags = [{"key": "items", "row": 1, "code": "row_arith"},
             {"key": "items", "code": "sum_mismatch"}]
    direct, broad = reprocess._rule_targets(flags, fields, quality)
    assert direct == {}
    assert {"items/0/amount", "items/1/amount"} <= broad
    reprocess._mark_rules(quality, direct)
    assert quality["items/1/name"]["status"] == "PASS"
    direct, _ = reprocess._rule_targets([{"key": "items", "row": 1, "column": "amount", "code": "bad"}], fields, quality)
    assert list(direct) == ["items/1/amount"]
    direct, broad = reprocess._rule_targets([{"key": "items", "column": "name", "code": "empty_column"}], fields, quality)
    assert direct == {} and broad == {"items/1/name"}


def test_equal_priority_keeps_schema_order_and_table_needs_cell_association(monkeypatch):
    _setup(monkeypatch)
    schema = {"properties": {"first": {}, "second": {}}}
    fields = {"first": "a", "second": "b"}
    monkeypatch.setattr(reprocess, "_quality", lambda *args: (
        {"first": {"status": "UNRESOLVED", "issue_codes": ["no_source"], "provenance": {}},
         "second": {"status": "UNRESOLVED", "issue_codes": ["no_source"], "provenance": {}}}, {}))
    _, _, _, summary = reprocess.run("scan.png", schema, [BLOCK], fields)
    assert summary["trace"][0]["field"] == "first"
    assert reprocess._positioned(_item(), [BLOCK], "items/0/amount") == 0
    assert reprocess._positioned({**_item(), "provenance": {**_item()["provenance"],
                                   "row": 0, "column": 1}}, [BLOCK], "items/0/amount") == 2
