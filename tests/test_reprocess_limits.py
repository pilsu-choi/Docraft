"""Public reprocess-loop boundaries: call budget, cancellation, and safe leaf updates."""

import threading
import time

import pytest

from backend import reprocess, verify


def configure(monkeypatch, *, calls=2, attempts=8):
    monkeypatch.setenv("REPROCESS_ENABLED", "true")
    monkeypatch.setenv("REPROCESS_MAX_MS", "10000")
    monkeypatch.setenv("REPROCESS_MAX_ATTEMPTS", str(attempts))
    monkeypatch.setenv("REPROCESS_MAX_MODEL_CALLS", str(calls))


def scalar_quality(fields, schema, blocks, grounds=None):
    quality = {}
    for key, value in fields.items():
        status = "UNRESOLVED" if value == "old" else "PASS"
        quality[key] = {"status": status, "provenance": {"match": "exact"} if status == "PASS" else {}}
    return quality, {}


def test_model_call_budget_counts_each_chunk_before_send(monkeypatch):
    configure(monkeypatch, calls=3)
    monkeypatch.setattr(reprocess, "_quality", scalar_quality)
    sent = []

    def extract(schema, blocks, source=None, *, on_call, **kwargs):
        root = next(iter(schema["properties"]))
        for _ in range(2):
            on_call()
            sent.append(root)
        return {root: "fixed"}, {}

    monkeypatch.setattr(reprocess.engine, "extract", extract)
    schema = {"type": "object", "properties": {"amount": {"type": "string"}, "other": {"type": "string"}}}
    blocks = [{"text": "amount other", "page": 1, "bbox": [1, 1, 20, 10], "page_size": [100, 100]}]
    fields, _, _, summary = reprocess.run(
        "unused.png", schema, blocks, {"amount": "old", "other": "old"}, enabled=True
    )

    assert summary["model_calls"] == 3
    assert len(sent) == 3  # the over-budget chunk was rejected before transport
    assert fields == {"amount": "fixed", "other": "old"}


def test_cancellation_before_provider_call_raises_without_sending(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(reprocess, "_quality", scalar_quality)
    sent = []
    monkeypatch.setattr(reprocess.engine, "extract", lambda *a, **k: sent.append(True))
    cancel = threading.Event()
    cancel.set()
    schema = {"type": "object", "properties": {"amount": {"type": "string"}}}

    with pytest.raises(verify.Cancelled):
        reprocess.run("unused.png", schema, [], {"amount": "old"}, cancel=cancel, enabled=True)
    assert sent == []


def test_late_candidate_is_discarded_after_extract_returns(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("REPROCESS_MIN_STAGE_MS", "0")  # start the call even with 10 ms left
    monkeypatch.setattr(reprocess, "_quality", scalar_quality)

    def late_extract(schema, blocks, source=None, **kwargs):
        kwargs["on_call"]()
        time.sleep(0.03)
        return {"amount": "fixed"}, {}

    monkeypatch.setattr(reprocess.engine, "extract", late_extract)
    schema = {"type": "object", "properties": {"amount": {"type": "string"}}}
    original = {"amount": "old"}
    blocks = [{"text": "amount", "page": 1, "bbox": [1, 1, 20, 10], "page_size": [100, 100]}]
    fields, _, _, summary = reprocess.run(
        "unused.png", schema, blocks, original, deadline=time.monotonic() + 0.01, enabled=True
    )

    assert fields == original
    assert summary["model_calls"] == 1
    assert summary["stop_reason"] == "deadline"
    assert not any(item.get("adopted") for item in summary["trace"])


def test_nested_scalar_candidate_updates_only_its_leaf(monkeypatch):
    configure(monkeypatch)
    calls = []

    def quality(fields, schema, blocks, grounds=None):
        status = "UNRESOLVED" if fields["person"]["name"] == "old" else "PASS"
        provenance = {"match": "exact"} if status == "PASS" else {}
        return {"person/name": {"status": status, "provenance": provenance}}, {}

    monkeypatch.setattr(reprocess, "_quality", quality)
    def extract(*args, **kwargs):
        calls.append(True)
        kwargs["on_call"]()
        return {"person": {"name": "new"}}, {}

    monkeypatch.setattr(reprocess.engine, "extract", extract)
    schema = {"type": "object", "properties": {"person": {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "string"}}}}}
    original = {"person": {"name": "old", "age": "kept"}}
    blocks = [{"text": "person", "page": 1, "bbox": [1, 1, 20, 10], "page_size": [100, 100]}]

    fields, _, quality_result, summary = reprocess.run(
        "unused.png", schema, blocks, original, enabled=True
    )

    assert fields == {"person": {"name": "new", "age": "kept"}}
    assert quality_result["person/name"]["status"] == "CORRECTED"
    assert summary["model_calls"] == 1
    assert calls == [True]
    assert summary["trace"][-1]["reason"] == "verified"


def test_table_candidate_matches_row_identity_and_patches_only_target_leaf(monkeypatch):
    configure(monkeypatch, calls=1)

    def quality(fields, schema, blocks, grounds=None):
        status = "PASS" if fields["items"][0]["amount"] == "correct" else "UNRESOLVED"
        provenance = {"match": "exact"} if status == "PASS" else {}
        return {"items/0/amount": {"status": status, "provenance": provenance}}, {}

    monkeypatch.setattr(reprocess, "_quality", quality)
    proposal = {"items": [
        {"name": "B", "amount": "untouched"},
        {"name": "A", "amount": "correct"},
    ]}
    def extract(*args, **kwargs):
        kwargs["on_call"]()
        return proposal, {}

    monkeypatch.setattr(reprocess.engine, "extract", extract)
    schema = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
        "name": {"type": "string"}, "amount": {"type": "string"}
    }}}}}
    original = {"items": [{"name": "A", "amount": "old"}, {"name": "B", "amount": "untouched"}]}

    fields, _, _, _ = reprocess.run("unused.png", schema, [], original, enabled=True)

    assert fields == {"items": [{"name": "A", "amount": "correct"}, {"name": "B", "amount": "untouched"}]}


def test_table_candidate_without_unique_identity_is_rejected(monkeypatch):
    configure(monkeypatch, calls=1)

    def quality(fields, schema, blocks, grounds=None):
        return {"items/0/amount": {"status": "UNRESOLVED", "provenance": {}}}, {}

    monkeypatch.setattr(reprocess, "_quality", quality)
    proposal = {"items": [{"amount": "guessed"}]}
    def extract(*args, **kwargs):
        kwargs["on_call"]()
        return proposal, {}

    monkeypatch.setattr(reprocess.engine, "extract", extract)
    schema = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"amount": {"type": "string"}}}}}}
    original = {"items": [{"amount": "old"}]}

    fields, _, _, summary = reprocess.run("unused.png", schema, [], original, enabled=True)

    assert fields == original  # a whole-array proposal cannot replace a table leaf by row index
    assert summary["trace"][-1]["reason"] == "no_safe_candidate"
