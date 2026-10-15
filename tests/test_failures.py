"""/api/read* 실패의 분류(408/502)·한 줄 요약·입력 보존, VLM 호출의 X-Request-ID·upstream·느린 호출 로그, 차트 렌더."""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

from backend import engine, failures, latency, verify
from backend.main import app
from backend.parsers import ParseError
from test_ai_provider import FakeClient, configure, install_response
from test_read_options import png  # noqa: F401  (fixture)
from test_verify import AO, _image, hinted_stub

client = TestClient(app)
REQUEST = httpx.Request("POST", "http://vllm/v1/chat/completions")
TIMEOUTS = [TimeoutError("late"), asyncio.TimeoutError(), httpx.ReadTimeout("t"), httpx.ConnectTimeout("t"), httpx.PoolTimeout("t"),
            httpx.WriteTimeout("t"), latency.Timeout("slot", "slot_wait"), latency.Timeout("shared", "shared_wait"),
            ParseError("PaddleOCR 원격 처리 실패")]
TIMEOUTS[-1].__cause__ = httpx.ReadTimeout("ocr")  # 래퍼 밑의 시간 초과도 408
UPSTREAM = [(engine.ProviderError("x", "http_500"), "http_500"), (engine.ProviderError("x", "format"), "format"),
            (httpx.HTTPStatusError("x", request=REQUEST, response=httpx.Response(503, request=REQUEST)), "http_503"),
            (httpx.ConnectError("refused"), "connect"), (httpx.RemoteProtocolError("closed"), "transport"),
            (json.JSONDecodeError("bad", "", 0), "format"), (RuntimeError("boom"), "error")]


def call(endpoint, monkeypatch, tmp_path, exc):
    """엔드포인트별로 VLM·OCR 단계가 ``exc``로 실패하게 하고 응답을 돌려준다."""
    hinted_stub(monkeypatch)

    def boom(*args, **kwargs):
        raise exc

    path = _image(tmp_path)
    for name in ("read", "run", "read_options"):
        monkeypatch.setattr(verify, name, boom)
    form = {"verify": {"ao_result": json.dumps(AO), "doc_type": "진단서"}, "read": {"doc_type": "진단서"}, "read-options": {"doc_type": "진단서"}}[endpoint]
    with open(path, "rb") as handle:
        return client.post(f"/api/{endpoint}", files={"image": (path.name, handle, "image/png")}, data=form)


@pytest.mark.parametrize("endpoint", ["read", "verify", "read-options"])
@pytest.mark.parametrize("exc", TIMEOUTS, ids=lambda exc: type(exc).__name__)
def test_every_timeout_kind_is_408_on_every_endpoint(monkeypatch, tmp_path, endpoint, exc):
    response = call(endpoint, monkeypatch, tmp_path, exc)

    assert response.status_code == 408 and "시간 초과" in response.json()["detail"]


@pytest.mark.parametrize("endpoint", ["read", "verify", "read-options"])
@pytest.mark.parametrize(("exc", "kind"), UPSTREAM, ids=lambda value: getattr(value, "__name__", None) or str(value)[:20])
def test_upstream_failures_are_502_with_their_kind(monkeypatch, tmp_path, endpoint, exc, kind):
    response = call(endpoint, monkeypatch, tmp_path, exc)

    assert response.status_code == 502 and f"({kind})" in response.json()["detail"]


def test_timeout_detail_names_the_kind_and_timeout():
    status, kind, timeout_s = failures.classify(latency.Timeout("x", "call_timeout", 19.0))

    assert (status, kind, timeout_s) == (408, "call_timeout", 19.0)
    assert "call_timeout, 19.0s" in failures.response(latency.Timeout("x", "call_timeout", 19.0), "읽기").detail


def test_remote_call_names_deadline_when_the_request_budget_ran_out():
    for deadline, kind in ((time.monotonic() - 1, "deadline"), (time.monotonic() + 60, "call_timeout"), (None, "call_timeout")):
        with pytest.raises(latency.Timeout) as caught, latency.remote_call(19.0, deadline):
            raise httpx.ReadTimeout("t")
        assert caught.value.kind == kind and caught.value.timeout_s == 19.0 and isinstance(caught.value, TimeoutError)


def test_parse_error_without_a_transport_cause_stays_422():
    assert failures.classify(ParseError("지원하지 않는 형식"))[0] == 422
    assert failures.response(ParseError("a"), "읽기", client_input=False).status_code == 502


def test_failure_line_carries_the_diagnostic_fields(monkeypatch, tmp_path, caplog):
    def slow(*args, **kwargs):
        with latency.timed("vlm_ms"):
            latency.note("vlm_calls", 2)
            latency.note("_upstream", "10.0.0.7:8000", add=False)
            raise latency.Timeout("ReadTimeout after 19.0s", "call_timeout", 19.0)

    hinted_stub(monkeypatch)
    monkeypatch.setattr(verify, "read", slow)
    path = _image(tmp_path)
    with caplog.at_level(logging.WARNING), open(path, "rb") as handle:
        response = client.post("/api/read", files={"image": (path.name, handle, "image/png")}, data={"doc_type": "진단서", "remaining_ms": "20000"})

    line = next(record.getMessage() for record in caplog.records if "read failed:" in record.getMessage())
    assert response.status_code == 408
    for field in ("endpoint=read", "doc_type=진단서", "status=408", "stage=vlm", "kind=call_timeout", "timeout_s=19.0", "budget_ms=20000",
                  "remaining_s=", "elapsed_ms=", "vlm_calls=2", "upstream=10.0.0.7:8000", "rid=", "vlm_ms="):
        assert field in line
    assert not any(record.exc_info for record in caplog.records if record.levelno >= logging.WARNING and "read failed" in record.getMessage())


def test_unexpected_errors_keep_the_traceback(monkeypatch, tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        call("read", monkeypatch, tmp_path, RuntimeError("boom"))

    assert any(record.exc_info and record.levelno == logging.ERROR for record in caplog.records if "read failed" in record.getMessage())


def test_diagnostics_hide_internal_notes(monkeypatch, png):  # noqa: F811
    monkeypatch.setattr(engine, "_provider", lambda *a, **k: latency.note("_upstream", "x", add=False) or {"section": True})
    response = client.post("/api/read-options", files={"image": ("a.png", png, "image/png")}, data={"doc_type": "진단서"})

    assert response.status_code == 200 and not any(key.startswith("_") for key in response.json()["diagnostics"])


# --- 실패 입력 보존 ------------------------------------------------------


@pytest.fixture
def failed_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(failures, "FAILED", tmp_path / "failed")
    monkeypatch.setattr(failures, "_pruned", float("-inf"))
    return tmp_path / "failed"


def flush_saves():
    failures._saver.submit(lambda: None).result()


def fail_read(monkeypatch, tmp_path, exc=latency.Timeout("w", "slot_wait"), rid="job/1:a b"):
    def boom(*args, **kwargs):
        latency.keep("_vlm_replies", {"call": "r#1", "raw": "{\"partial\": true}"})
        raise exc

    hinted_stub(monkeypatch)
    monkeypatch.setattr(verify, "read", boom)
    path = _image(tmp_path)
    with open(path, "rb") as handle:
        response = client.post("/api/read", headers={"X-Request-ID": rid}, files={"image": (path.name, handle, "image/png")},
                               data={"doc_type": "진단서", "keys": json.dumps(["진단일"], ensure_ascii=False), "remaining_ms": "5000"})
    flush_saves()
    return response


def test_failed_read_keeps_inputs_meta_and_partial_replies(monkeypatch, tmp_path, failed_dir):
    response = fail_read(monkeypatch, tmp_path)

    folder = next(failed_dir.glob("*/*"))
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    assert response.status_code == 408 and folder.parent.name == datetime.now().strftime("%Y%m%d") and "/" not in folder.name
    assert (folder / "input.png").read_bytes() == (tmp_path / "scan.png").read_bytes()
    assert meta["params"]["keys"] == '["진단일"]' and meta["params"]["remaining_ms"] == 5000 and meta["kind"] == "slot_wait" and "kind=slot_wait" in meta["line"]
    assert json.loads((folder / "vlm_replies.json").read_text(encoding="utf-8"))[0]["raw"] == '{"partial": true}'


@pytest.mark.parametrize("rid", [".", "..", "...", "_._"])
def test_dot_only_request_ids_never_become_the_folder_name(monkeypatch, tmp_path, failed_dir, rid):
    assert fail_read(monkeypatch, tmp_path, rid=rid).status_code == 408

    folder = next(failed_dir.glob("*/*"))
    assert folder.parent.parent == failed_dir and folder.name.startswith("norid-") and (folder / "input.png").exists()


def test_same_request_id_failures_keep_separate_folders(monkeypatch, tmp_path, failed_dir):
    for _ in range(3):  # 하네스 rid(job.txn.doc)는 페이지·재시도마다 같다
        fail_read(monkeypatch, tmp_path, rid="job.1.doc")

    folders = list(failed_dir.glob("*/*"))
    assert len(folders) == 3 and all(f.name.startswith("job.1.doc-") for f in folders)


def test_fail_returns_before_the_save_and_the_save_still_happens(monkeypatch, tmp_path, failed_dir):
    import threading

    gate, started = threading.Event(), threading.Event()
    real = failures.Call._save

    def slow(self, *args):
        started.set()
        gate.wait(5)
        real(self, *args)

    monkeypatch.setattr(failures.Call, "_save", slow)
    call = failures.Call("read", None, None, time.monotonic() + 5, upload=(".png", b"x"))
    began = time.monotonic()
    error = call.fail(RuntimeError("boom"), {}, "읽기")
    assert time.monotonic() - began < 0.5 and error.status_code == 502 and not failed_dir.exists()
    gate.set()
    flush_saves()
    assert (next(failed_dir.glob("*/*")) / "input.png").read_bytes() == b"x"


def test_prune_runs_at_most_once_a_minute(monkeypatch, tmp_path, failed_dir):
    runs = []
    monkeypatch.setattr(failures, "prune", lambda: runs.append(1))
    for _ in range(3):
        fail_read(monkeypatch, tmp_path)

    assert len(runs) == 1


def test_keeping_is_off_at_zero_days(monkeypatch, tmp_path, failed_dir):
    monkeypatch.setenv("FAILED_KEEP_DAYS", "0")

    assert fail_read(monkeypatch, tmp_path).status_code == 408 and not failed_dir.exists()


def test_a_save_failure_does_not_hide_the_original_error(monkeypatch, tmp_path, failed_dir, caplog):
    monkeypatch.setattr(failures, "FAILED", tmp_path / "scan.png" / "no")  # 파일 밑이라 mkdir이 실패한다
    with caplog.at_level(logging.WARNING):
        response = fail_read(monkeypatch, tmp_path)

    assert response.status_code == 408 and "시간 초과" in response.json()["detail"] and "failed-input save skipped" in caplog.text


def test_prune_drops_days_beyond_keep_days_and_oldest_beyond_the_size_cap(monkeypatch, failed_dir):
    def entry(day, name, size, age):
        folder = failed_dir / day.strftime("%Y%m%d") / name
        folder.mkdir(parents=True)
        (folder / "input.png").write_bytes(b"x" * size)
        os.utime(folder, (time.time() - age, time.time() - age))
        return folder

    today = datetime.now()
    old, oldest, newer, newest = (entry(today - timedelta(days=9), "old", 10, 900), entry(today, "a", 600_000, 30), entry(today, "b", 600_000, 20), entry(today, "c", 100, 10))
    monkeypatch.setenv("FAILED_KEEP_DAYS", "7")
    monkeypatch.setenv("FAILED_MAX_MB", "1")

    failures.prune()

    assert not old.exists() and not oldest.exists() and newer.exists() and newest.exists()
    monkeypatch.setenv("FAILED_KEEP_DAYS", "0")
    failures.prune()
    assert not list(failed_dir.glob("*/*"))


def test_replay_resends_the_saved_inputs(monkeypatch, tmp_path, failed_dir):
    import runpy
    import sys

    fail_read(monkeypatch, tmp_path)
    folder = next(failed_dir.glob("*/*"))
    sent = {}

    def fake_post(url, data, files, headers, timeout):
        sent.update(url=url, data=data, name=files["image"][0])
        return httpx.Response(200, text="ok")

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(sys, "argv", ["replay", str(folder), "--remaining-ms", "99000"])
    runpy.run_module("backend.replay", run_name="__main__")

    assert sent["url"].endswith("/api/read") and sent["data"]["doc_type"] == "진단서" and sent["data"]["remaining_ms"] == "99000" and sent["name"] == "input.png"


# --- VLM 호출: X-Request-ID·upstream·느린 호출 -----------------------------


def reply(upstream="10.0.0.7:8000"):
    install_response_data = httpx.Response(200, json={"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}], "usage": {"completion_tokens": 7}},
                                           headers={"x-upstream-host": upstream} if upstream else {}, request=REQUEST)
    FakeClient.response, FakeClient.responses, FakeClient.requests = install_response_data, None, []


def test_vlm_calls_forward_rid_with_a_call_index_and_note_the_upstream(monkeypatch):
    configure(monkeypatch)
    reply()
    monkeypatch.setattr(engine.httpx, "Client", FakeClient)
    from backend.config import bind_request

    with bind_request("rid42"), latency.track() as stages:
        engine._provider([{"role": "user", "content": "a"}])
        engine._provider([{"role": "user", "content": "b"}])

    assert [kwargs["headers"]["X-Request-ID"] for _, kwargs in FakeClient.requests] == ["rid42#1", "rid42#2"]
    assert stages["_upstream"] == "10.0.0.7:8000" and len(stages["_vlm_replies"]) == 2 and stages["vlm_calls"] == 2


def test_no_request_id_header_outside_a_request(monkeypatch):
    configure(monkeypatch)
    reply(None)
    monkeypatch.setattr(engine.httpx, "Client", FakeClient)

    engine._provider([{"role": "user", "content": "a"}])

    assert "X-Request-ID" not in FakeClient.requests[0][1]["headers"]


@pytest.mark.parametrize(("slow_ms", "level"), [("0", logging.INFO), ("3600000", logging.DEBUG)])
def test_slow_vlm_calls_log_at_info_with_their_facts(monkeypatch, caplog, slow_ms, level):
    configure(monkeypatch)
    reply()
    monkeypatch.setenv("VLM_SLOW_MS", slow_ms)
    monkeypatch.setattr(engine.httpx, "Client", FakeClient)

    with caplog.at_level(logging.DEBUG, logger=engine.logger.name):
        engine._provider([{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}, {"type": "text", "text": "hello"}]}])

    record = next(r for r in caplog.records if r.getMessage().startswith("vlm call "))
    assert record.levelno == level
    for field in ("images=1/", "prompt_chars=5", "finish_reason=stop", "completion_tokens=7", "upstream=10.0.0.7:8000", "elapsed=", "timeout_s="):
        assert field in record.getMessage()


@pytest.mark.parametrize(("status", "kind"), [(500, "http_500"), (503, "http_503")])
def test_failed_vlm_call_logs_a_warning_and_raises_a_provider_error(monkeypatch, caplog, status, kind):
    configure(monkeypatch)
    install_response(monkeypatch, "{}", status_code=status)

    with caplog.at_level(logging.WARNING), pytest.raises(engine.ProviderError) as caught:
        engine._provider([{"role": "user", "content": "a"}])

    assert caught.value.kind == kind and f"vlm call failed: call=" in caplog.text and f"kind={kind}" in caplog.text


# --- 차트 ----------------------------------------------------------------

CHART = Path(__file__).resolve().parent.parent / "deploy/k8s/helm/docraft"


@pytest.fixture(scope="module")
def rendered():
    if not shutil.which("helm"):
        pytest.skip("helm 없음")
    out = subprocess.run(["helm", "template", "t", str(CHART), "--set", "vllmVlm.enabled=true", "--set", "vllmVlm.parallel=replicas",
                          "--set", "paddleocrVl.enabled=true", "--set", "paddleocrLines.enabled=true", "--set", "frontend.enabled=true",
                          "--set", "worker.enabled=true", "--set", "master.sourceImage.repository=m", "--set", "master.sourceImage.tag=1"],
                         check=True, capture_output=True, text=True).stdout
    return [doc for doc in yaml.safe_load_all(out) if doc]


def pod_specs(docs):
    return [(doc["metadata"]["name"], doc["spec"]["template"]["spec"] if doc["kind"] == "Deployment" else doc["spec"]) for doc in docs if doc["kind"] in ("Deployment", "Pod")]


def test_every_container_has_ephemeral_storage_and_every_emptydir_a_size_limit(rendered):
    for name, spec in pod_specs(rendered):
        for container in spec.get("containers", []) + spec.get("initContainers", []):
            for side in ("requests", "limits"):
                assert "ephemeral-storage" in container["resources"][side], (name, container["name"], side)
        for volume in spec.get("volumes", []):
            assert "emptyDir" not in volume or "sizeLimit" in volume["emptyDir"], (name, volume["name"])


EPHEMERAL_REQUEST_BUDGET_GI = 6  # 3장 replicas 프로파일의 ephemeral-storage requests 합 상한 — 노드 allocatable(고객사 ~38GB)에 걸려 Pending 되지 않게


def gi(quantity):
    return float(quantity[:-2]) * {"Gi": 1, "Mi": 1 / 1024}[quantity[-2:]]


def test_ephemeral_storage_requests_of_a_three_card_profile_stay_within_budget():
    if not shutil.which("helm"):
        pytest.skip("helm 없음")
    out = subprocess.run(["helm", "template", "t", str(CHART), "--set", "vllmVlm.enabled=true", "--set", "vllmVlm.parallel=replicas",
                          "--set", "vllmVlm.gpuCount=3", "--set", "paddleocrVl.enabled=true", "--set", "paddleocrVl.apiReplicas=3",
                          "--set", "paddleocrLines.enabled=true", "--set", "frontend.enabled=true", "--set", "worker.enabled=true",
                          "--set", "backend.replicas=2", "--set", "master.sourceImage.repository=m", "--set", "master.sourceImage.tag=1"],
                         check=True, capture_output=True, text=True).stdout
    total = 0
    for doc in (d for d in yaml.safe_load_all(out) if d and d["kind"] == "Deployment"):
        spec = doc["spec"]["template"]["spec"]
        request = lambda c: gi(c["resources"]["requests"]["ephemeral-storage"])
        pod = max(sum(map(request, spec["containers"])), *map(request, spec.get("initContainers", [])), 0)  # 파드 유효 request = max(init, 컨테이너 합)
        total += pod * doc["spec"].get("replicas", 1)
    assert total <= EPHEMERAL_REQUEST_BUDGET_GI, total


def test_vllm_keeps_a_high_ephemeral_limit_for_compile_caches(rendered):
    vllm = next(c for name, spec in pod_specs(rendered) if "vllm-vlm" in name for c in spec["containers"] if c["name"] == "vllm")

    assert vllm["resources"]["limits"]["ephemeral-storage"] == "30Gi"


def test_chart_passes_the_observability_settings_to_the_backend_and_envoy(rendered):
    env = next(doc for doc in rendered if doc["kind"] == "ConfigMap" and doc["metadata"]["name"].endswith("-env"))["data"]
    envoy = next(doc for doc in rendered if doc["kind"] == "ConfigMap" and doc["metadata"]["name"].endswith("-vllm-router"))["data"]["envoy.yaml"]

    assert (env["FAILED_KEEP_DAYS"], env["FAILED_MAX_MB"], env["VLM_SLOW_MS"]) == ("7", "2048", "15000")
    config = yaml.safe_load(envoy)
    manager = config["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]
    log = manager["access_log"][0]["typed_config"]["log_format"]["text_format_source"]["inline_string"]
    route = manager["route_config"]["virtual_hosts"][0]["routes"][0]
    assert log.count("\n") == 1 and log.endswith("\n")
    for token in ("%REQ(X-REQUEST-ID)%", "%UPSTREAM_TRANSPORT_FAILURE_REASON%", "%BYTES_RECEIVED%", "%BYTES_SENT%", "%UPSTREAM_REQUEST_ATTEMPT_COUNT%"):
        assert token in log
    assert route["response_headers_to_add"][0]["header"] == {"key": "x-upstream-host", "value": "%UPSTREAM_REMOTE_ADDRESS%"}
