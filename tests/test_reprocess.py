"""Recovery decisions must preserve unrelated values and require renewed evidence."""

from fastapi.testclient import TestClient
from PIL import Image

from backend import reprocess
from backend.main import app


SCHEMA = {"type": "object", "properties": {"amount": {"type": "string", "title": "amount"},
                                               "other": {"type": "string", "title": "other"}}}
BLOCK = {"text": "amount", "page": 1, "bbox": [10, 10, 80, 30], "page_size": [200, 100]}


def quality(fields, schema, blocks, grounds=None):
    recovered = fields["amount"] == "new" or any(block.get("recovered") for block in blocks)
    state = "PASS" if recovered else "UNRESOLVED"
    return {"amount": {"status": state, "provenance": {"match": "exact"} if recovered else {}},
            "other": {"status": "PASS", "provenance": {"match": "exact"}}}, {}


def setup(monkeypatch, *, calls=2):
    monkeypatch.setenv("REPROCESS_ENABLED", "true")
    monkeypatch.setenv("REPROCESS_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("REPROCESS_MAX_MODEL_CALLS", str(calls))
    monkeypatch.setenv("REPROCESS_MAX_MS", "10000")
    monkeypatch.setattr(reprocess, "_quality", quality)
    monkeypatch.setattr(reprocess, "_crop", lambda *args: (0, 0, 200, 100))


def test_roi_vlm_corrects_one_leaf_and_keeps_other_value(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(reprocess, "parse", lambda *a, **k: ("", [BLOCK]))
    called = []
    def extract(schema, blocks, source=None, *, on_call, **kwargs):
        on_call()
        called.append(source)
        return {"amount": "new"}, {}
    monkeypatch.setattr(reprocess.engine, "extract", extract)
    initial = {"amount": "old", "other": "kept"}

    fields, _, assessed, summary = reprocess.run("scan.png", SCHEMA, [BLOCK], initial,
                                                  normalize=lambda values, blocks: values)

    assert fields == {"amount": "new", "other": "kept"}
    assert assessed["amount"]["status"] == "CORRECTED"
    assert summary["status"] == "CORRECTED" and summary["extra_model_calls"] == 1
    adopted = [step for step in summary["trace"] if step["adopted"]]
    assert len(adopted) == 1 and adopted[0]["before"] == "old" and adopted[0]["proposed"] == "new"
    assert len(called) == 1 and called[0].endswith("roi.png")


def test_wider_vlm_runs_once_when_roi_unavailable(monkeypatch):
    setup(monkeypatch, calls=1)
    monkeypatch.setattr(reprocess, "_crop", lambda *args: None)
    called = []
    def extract(schema, blocks, source=None, *, on_call, **kwargs):
        on_call()
        called.append(source)
        return {"amount": "new"}, {}
    monkeypatch.setattr(reprocess.engine, "extract", extract)

    fields, _, _, summary = reprocess.run("scan.png", SCHEMA, [BLOCK], {"amount": "old", "other": "kept"})

    assert fields["amount"] == "new"
    assert called == ["scan.png"]
    assert any(step["stage"] == "wide_vlm" and step["adopted"] for step in summary["trace"])


def test_candidate_with_new_rule_error_is_rejected(monkeypatch):
    setup(monkeypatch, calls=1)
    monkeypatch.setattr(reprocess, "_crop", lambda *args: None)
    def extract(*args, **kwargs):
        kwargs["on_call"]()
        return {"amount": "new"}, {}
    monkeypatch.setattr(reprocess.engine, "extract", extract)
    def check_rules(values, evidence):
        return [{"key": "amount", "code": "sum_mismatch"}] if values["amount"] == "new" else []

    fields, _, _, summary = reprocess.run("scan.png", SCHEMA, [BLOCK], {"amount": "old", "other": "kept"},
                                          check_rules=check_rules)

    assert fields["amount"] == "old" and summary["status"] == "UNRESOLVED"
    assert any(step["proposed"] == "new" and not step["adopted"] for step in summary["trace"])


def test_same_value_can_gain_evidence_without_being_called_a_correction(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(reprocess, "parse", lambda *a, **k: ("", [{**BLOCK, "recovered": True}]))
    monkeypatch.setattr(reprocess.engine, "extract", lambda *a, **k: (_ for _ in ()).throw(AssertionError("VLM unnecessary")))

    fields, _, assessed, summary = reprocess.run(
        "scan.png", SCHEMA, [BLOCK], {"amount": "old", "other": "kept"},
        normalize=lambda values, blocks: values)

    assert fields["amount"] == "old" and assessed["amount"]["status"] == "PASS"
    assert summary["model_calls"] == 0
    assert any(step["adopted"] and step["before"] == step["after"] for step in summary["trace"])


def test_server_disable_has_precedence_and_expired_api_budget_skips_read(monkeypatch, tmp_path):
    setup(monkeypatch)
    monkeypatch.setenv("REPROCESS_ENABLED", "false")
    monkeypatch.setattr(reprocess.engine, "extract", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no extra model")))
    _, _, _, summary = reprocess.run("scan.png", SCHEMA, [BLOCK], {"amount": "old", "other": "kept"}, enabled=True)
    assert summary["stop_reason"] == "disabled" and summary["model_calls"] == 0

    from backend import verify
    monkeypatch.setattr(verify, "read", lambda *a, **k: (_ for _ in ()).throw(AssertionError("initial read must not start")))
    path = tmp_path / "scan.png"
    Image.new("RGB", (8, 8), "white").save(path)
    with path.open("rb") as image:
        response = TestClient(app).post("/api/read", files={"image": (path.name, image, "image/png")},
                                        data={"doc_type": "진단서", "remaining_ms": "0"})
    assert response.status_code == 408


def test_nested_object_at_three_segments_still_needs_a_label(monkeypatch):
    setup(monkeypatch, calls=1)
    monkeypatch.setattr(reprocess, "_crop", lambda *args: None)
    schema = {"type": "object", "properties": {"person": {"type": "object", "properties": {
        "contact": {"type": "object", "properties": {"name": {"type": "string"}}}}}}}
    initial = {"person": {"contact": {"name": "old"}}}
    monkeypatch.setattr(reprocess, "_quality", lambda fields, *a: (
        {"person/contact/name": {"status": "PASS" if fields["person"]["contact"]["name"] == "new" else "UNRESOLVED",
                                 "provenance": {"match": "exact"}}}, {}))
    def extract(*a, **k):
        k["on_call"]()
        return {"person": {"contact": {"name": "new"}}}, {}
    monkeypatch.setattr(reprocess.engine, "extract", extract)

    fields, _, _, summary = reprocess.run("scan.png", schema, [{**BLOCK, "text": "unrelated"}], initial)

    assert fields == initial
    assert summary["trace"][-1]["checks"]["semantic"] is False


def test_same_rule_code_in_another_row_is_a_new_error(monkeypatch):
    setup(monkeypatch, calls=1)
    monkeypatch.setattr(reprocess, "_crop", lambda *args: None)
    monkeypatch.setattr(reprocess.engine, "extract", lambda *a, **k: (k["on_call"]() or {"amount": "new"}, {}))
    def check_rules(values, blocks):
        return [{"rule": "SUM", "key": "amount", "code": "sum_mismatch",
                 "row": 1 if values["amount"] == "new" else 0}]

    fields, _, _, summary = reprocess.run("scan.png", SCHEMA, [BLOCK],
                                          {"amount": "old", "other": "kept"}, check_rules=check_rules)

    assert fields["amount"] == "old"
    assert summary["trace"][-1]["checks"]["rules"] is False


def test_two_adoptions_keep_both_corrected_markers(monkeypatch):
    setup(monkeypatch, calls=2)
    monkeypatch.setattr(reprocess, "_crop", lambda *args: None)
    both = {**BLOCK, "text": "amount other"}
    def two_quality(fields, *args):
        return ({key: {"status": "PASS" if value == "new" else "UNRESOLVED",
                       "provenance": {"match": "exact"} if value == "new" else {}}
                 for key, value in fields.items()}, {})
    monkeypatch.setattr(reprocess, "_quality", two_quality)
    def extract(schema, blocks, source=None, *, on_call, **kwargs):
        on_call()
        return {next(iter(schema["properties"])): "new"}, {}
    monkeypatch.setattr(reprocess.engine, "extract", extract)

    fields, _, assessed, summary = reprocess.run("scan.png", SCHEMA, [both],
                                                 {"amount": "old", "other": "old"})

    assert fields == {"amount": "new", "other": "new"}
    assert assessed["amount"]["status"] == assessed["other"]["status"] == "CORRECTED"
    assert summary["extra_model_calls"] == 2


def test_roi_vlm_does_not_override_value_that_roi_ocr_read_unchanged(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(reprocess, "parse", lambda *a, **k: ("", [{**BLOCK, "text": "old"}]))
    monkeypatch.setattr(reprocess.engine, "extract", lambda *a, on_call, **k: (on_call(), ({"amount": "new"}, {}))[1])

    fields, _, _, summary = reprocess.run("scan.png", SCHEMA, [BLOCK], {"amount": "old", "other": "kept"},
                                          normalize=lambda values, blocks: values)

    assert fields["amount"] == "old"
    assert not any(step["adopted"] for step in summary["trace"])
    assert any(step["reason"] == "roi_parse_supports_original" for step in summary["trace"])
