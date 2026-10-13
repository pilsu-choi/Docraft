"""끊긴 keep-alive 연결 재사용: 응답 전 오류만 한 번 다시 보낸다."""

import httpx
import pytest

from backend import latency


class _Fake:
    """HTTPTransport.handle_request를 대신하는 시나리오: 항목이 예외면 던지고 아니면 응답으로 돌려준다."""

    def __init__(self, *steps):
        self.steps, self.calls = list(steps), 0

    def __call__(self, request):
        self.calls += 1
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def _client(monkeypatch, *steps):
    fake = _Fake(*steps)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", lambda self, request: fake(request))
    return latency.http_client.__wrapped__(0), fake


def _ok():
    return httpx.Response(200, content=b"ok")


@pytest.mark.parametrize("error", [httpx.RemoteProtocolError("Server disconnected"), httpx.ReadError("reset")])
@pytest.mark.parametrize("stream", [False, True])
def test_retries_once_when_connection_was_stale(monkeypatch, error, stream):
    client, fake = _client(monkeypatch, error, _ok())
    if stream:
        with client.stream("POST", "http://x/v1", json={}) as response:
            assert response.read() == b"ok"
    else:
        assert client.post("http://x/v1", json={}).content == b"ok"
    assert fake.calls == 2


def test_error_propagates_after_second_failure(monkeypatch):
    client, fake = _client(monkeypatch, httpx.RemoteProtocolError("a"), httpx.RemoteProtocolError("b"))
    with pytest.raises(httpx.RemoteProtocolError):
        client.post("http://x/v1", json={})
    assert fake.calls == 2


def test_error_after_headers_is_not_retried(monkeypatch):
    class Broken(httpx.SyncByteStream):
        def __iter__(self):
            raise httpx.RemoteProtocolError("peer closed mid-body")

    client, fake = _client(monkeypatch, httpx.Response(200, stream=Broken()), _ok())
    with pytest.raises(httpx.RemoteProtocolError):
        client.post("http://x/v1", json={})
    assert fake.calls == 1


def test_other_errors_are_not_retried(monkeypatch):
    client, fake = _client(monkeypatch, httpx.ReadTimeout("slow"), _ok())
    with pytest.raises(httpx.ReadTimeout):
        client.post("http://x/v1", json={})
    assert fake.calls == 1


def test_keepalive_expiry_is_below_server_default():
    pool = latency.http_client(0)._transport._pool
    assert pool._keepalive_expiry < 5.0  # uvicorn timeout_keep_alive 기본 5초
