"""/api/read 지연 대응: 같은 페이지 결과 공유, GPU OCR 자리, 표 교정 분할, 재처리·모델 호출 시한."""

import json
import threading
import time

import httpx
import pytest
from PIL import Image

from backend import engine, latency, parsers, reprocess


@pytest.fixture
def cache(monkeypatch):
    monkeypatch.setenv("READ_CACHE_SIZE", "4")
    monkeypatch.setenv("READ_CACHE_TTL_S", "60")
    monkeypatch.setattr(latency, "_cache", latency.OrderedDict())
    monkeypatch.setattr(latency, "_flights", {})


def test_concurrent_same_key_computes_once_and_shares_copies(cache):
    calls, started, results = [], threading.Event(), {}

    def compute():
        calls.append(1)
        started.set()
        time.sleep(0.1)
        return {"blocks": [1]}

    def request(name):
        with latency.track() as stats:
            results[name] = latency.shared("page", compute, time.monotonic() + 5), stats

    leader = threading.Thread(target=request, args=("leader",))
    leader.start()
    started.wait(1)
    follower = threading.Thread(target=request, args=("follower",))
    follower.start()
    leader.join(), follower.join()

    assert len(calls) == 1
    assert results["leader"][0] == results["follower"][0] == {"blocks": [1]}
    assert results["leader"][0] is not results["follower"][0]
    assert results["leader"][1]["cache_hit"] is False and results["follower"][1]["cache_hit"] is True


def test_cache_hit_keeps_the_page_call_not_later_crop_calls(cache):
    latency.shared("page", lambda: {"blocks": [1]})
    with latency.track() as stats:
        latency.shared("page", lambda: {"blocks": [1]})  # 페이지 OCR — 다른 요청이 이미 계산
        latency.shared("crop", lambda: {"blocks": [2]})  # 재처리 크롭 재OCR — 새로 계산
    assert stats["cache_hit"] is True


def test_failed_leader_is_not_shared_the_waiter_computes_again(cache):
    attempts, started = [], threading.Event()

    def compute():
        attempts.append(1)
        if len(attempts) == 1:
            started.set()
            time.sleep(0.05)
            raise TimeoutError("leader deadline")
        return "ok"

    errors = []
    leader = threading.Thread(target=lambda: errors.append(pytest.raises(TimeoutError, latency.shared, "k", compute)))
    leader.start()
    started.wait(1)
    assert latency.shared("k", compute, time.monotonic() + 5) == "ok"
    leader.join()
    assert len(attempts) == 2


def test_ocr_slot_wait_past_deadline_is_a_timeout(monkeypatch, tmp_path):
    monkeypatch.setenv("OCR_CONCURRENCY", "1")
    monkeypatch.setattr(latency, "_ocr_gate", None)
    monkeypatch.setenv("PADDLEOCR_BASE_URL", "https://ocr.invalid")
    monkeypatch.setattr(parsers.httpx, "post", lambda *a, **k: pytest.fail("OCR must not be called without a slot"))
    source = tmp_path / "scan.png"
    source.write_bytes(b"image")
    with latency.ocr_slot():  # another request holds the only GPU slot
        started = time.monotonic()
        with latency.track() as stats, pytest.raises(TimeoutError):
            parsers._remote_paddle(source, 1, expected_pages=1, deadline=time.monotonic() + 0.1)
    assert time.monotonic() - started < 1
    assert stats["ocr_wait_ms"] >= 90


def _table(rows):
    return "<table>" + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows) + "</table>"


def test_split_refine_merges_to_the_unsplit_result(monkeypatch, tmp_path):
    path = tmp_path / "scan.png"
    Image.new("RGB", (100, 100), "white").save(path)
    monkeypatch.setenv("AI_MODE", "provider")
    monkeypatch.setenv("TABLE_REFINE", "true")
    monkeypatch.setenv("AI_BASE_URL", "http://ai.invalid")
    monkeypatch.setenv("AI_API_KEY", "key")
    monkeypatch.setenv("AI_VLM_MODEL", "vlm")
    monkeypatch.setenv("REFINE_CONCURRENCY", "3")
    rows = [[f"항목{r}", f"{r}0O0", "<img src=seal.png>" if r == 2 else f"비고{r}"] for r in range(7)]
    blocks = [{"type": "table", "page": 1, "bbox": [0, 0, 100, 100], "page_size": [100, 100], "text": _table(rows)},
              {"type": "table", "page": 1, "bbox": [0, 0, 50, 50], "page_size": [100, 100], "text": _table([["합계", "1O"]])}]
    sent = []

    def provider(messages, timeout, timeout_cap=None):
        text = messages[0]["content"][-1]["text"]
        cells = json.loads(text[text.rindex("\n\n") + 2:].removeprefix(engine.TABLE_PART_NOTE))
        sent.append(cells)
        return {"corrections": {number: value.replace("O", "0") for number, value in cells.items()}}

    monkeypatch.setattr(engine, "_provider", provider)
    monkeypatch.setenv("REFINE_MAX_CELLS", "0")
    whole = engine.refine_tables(blocks, str(path))
    assert len(sent) == 2
    sent.clear()
    monkeypatch.setenv("REFINE_MAX_CELLS", "6")  # whole rows of 3 cells: rows 0-1, 2-3 (cell 8 is an image), 4-5, 6
    split = engine.refine_tables(blocks, str(path))

    assert split == whole and "<td>1000</td>" in whole[0] and whole[1].endswith("<td>10</td></tr></table>")
    assert len(sent) == 5 and all(len(part) <= 6 for part in sent)
    assert sorted(int(number) for part in sent for number in part) == sorted([n for n in range(21) if n != 8] + [0, 1])


def test_reprocess_does_not_start_a_remote_stage_with_little_time_left(monkeypatch):
    monkeypatch.setenv("REPROCESS_MAX_MS", "60000")
    monkeypatch.setenv("REPROCESS_MIN_STAGE_MS", "30000")
    monkeypatch.setattr(reprocess, "_quality", lambda fields, *a, **k: (
        {"amount": {"status": "UNRESOLVED" if fields["amount"] == "old" else "PASS", "provenance": {}}}, {}))
    monkeypatch.setattr(reprocess.engine, "extract", lambda *a, **k: pytest.fail("no VLM call may start"))
    blocks = [{"text": "amount", "page": 1, "bbox": [1, 1, 20, 10], "page_size": [100, 100]}]
    schema = {"type": "object", "properties": {"amount": {"type": "string"}}}

    fields, _, _, summary = reprocess.run("unused.png", schema, blocks, {"amount": "old"},
                                          deadline=time.monotonic() + 10, enabled=True)

    assert fields == {"amount": "old"} and summary["stop_reason"] == "deadline" and summary["model_calls"] == 0


def test_provider_keep_alive_cannot_outlive_the_deadline(monkeypatch):
    monkeypatch.setenv("AI_MODE", "provider")
    monkeypatch.setenv("AI_BASE_URL", "https://provider.invalid/v1")
    monkeypatch.setenv("AI_API_KEY", "key")
    monkeypatch.setenv("AI_VLM_MODEL", "vlm")

    def keep_alive():  # OpenRouter streams whitespace until the answer is ready, so no read timeout ever fires
        for _ in range(50):
            time.sleep(0.05)
            yield b" "

    real_client = httpx.Client
    monkeypatch.setattr(engine.httpx, "Client", lambda **_: real_client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=keep_alive()))))
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        engine._provider([{"role": "user", "content": "JSON"}], timeout_cap=0.2)
    assert time.monotonic() - started < 1
