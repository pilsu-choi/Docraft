"""요청 지연을 줄이는 프로세스 공용 장치: 같은 페이지 결과 공유, GPU OCR·VLM 동시성 제한, 병렬 호출, 단계별 시간 집계.

하네스는 같은 페이지의 필드 요청과 표 요청을 동시에 보낸다. ``shared``는 그 둘이 OCR·표 교정을 한 번만 하게 하고,
``ocr_slot``·``provider_slot``은 포화된 GPU에 요청이 몰려 모두 느려지는 대신 줄을 세운다. ``track``으로 묶은 요청은 ``timed``·
``ocr_slot``·``shared``가 남긴 단계별 시간을 한 dict로 모은다(``read finished`` 로그 줄).
"""

import contextvars
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager, suppress
from copy import deepcopy
from functools import lru_cache

import httpx

from .config import limit

_stats: contextvars.ContextVar[dict | None] = contextvars.ContextVar("docraft_stats", default=None)
_lock = threading.Lock()
_cache: OrderedDict = OrderedDict()  # key -> (만료 시각, 값)
_flights: dict = {}  # 계산 중인 key -> 끝나면 세워지는 Event
_gates: dict[str, threading.BoundedSemaphore] = {}  # 환경변수 이름 -> 자리(첫 호출 때 크기 고정)
_background = ThreadPoolExecutor(32, thread_name_prefix="docraft-early")  # ``spawn``: 기다리는 동안 먼저 보내 두는 원격 호출


class _RetryStaleTransport(httpx.HTTPTransport):
    """서버가 이미 닫은 keep-alive 연결을 재사용해 응답 전에 끊기면(RemoteProtocolError·ReadError) 새 연결로 한 번 다시 보낸다.
    응답 헤더를 받은 뒤의 오류는 handle_request 밖에서 나므로 재시도하지 않는다. ``retries``(연결 실패 재시도)와 별개다."""

    def handle_request(self, request):
        try:
            return super().handle_request(request)
        except (httpx.RemoteProtocolError, httpx.ReadError):
            return super().handle_request(request)


@lru_cache
def http_client(retries=0):
    """프로세스 공용 HTTP 클라이언트(스레드 안전): 호출마다 연결·TLS를 새로 맺지 않는다. 연결 수는 제한하지 않아(동시성은 슬롯이 정한다)
    VLM·OCR 동시 호출이 풀에서 기다리지 않는다. 시한은 호출마다 `timeout=`으로 준다.
    유휴 연결은 2초만 쓴다: uvicorn(vLLM·Docraft·하네스)의 keep-alive 5초와 같으면 닫히는 순간과 재사용이 겹친다."""
    limits = httpx.Limits(max_connections=None, max_keepalive_connections=32, keepalive_expiry=2.0)
    return httpx.Client(transport=_RetryStaleTransport(retries=retries, limits=limits))


class Timeout(TimeoutError):
    """시간 초과의 종류(``kind``)와 적용한 timeout(초)을 싣는다 — 종류가 없는 TimeoutError는 ``deadline``(요청 시한 소진)으로 본다.
    call_timeout(호출 한 번의 timeout) | deadline(요청 시한) | slot_wait(OCR·VLM 자리 대기) | shared_wait(같은 페이지 결과 대기) |
    connect_timeout | pool_timeout."""

    def __init__(self, message, kind="deadline", timeout_s=None):
        super().__init__(message)
        self.kind, self.timeout_s = kind, timeout_s


@contextmanager
def remote_call(timeout, deadline=None):
    """원격 호출 안의 httpx 시간 초과를 ``Timeout``으로 바꾼다(httpx.ReadTimeout은 TimeoutError가 아니다). 요청 ``deadline``이 이미 지났거나
    1초 안이면 호출 timeout이 시한으로 잘린 것이라 종류는 deadline이다."""
    try:
        yield
    except httpx.TimeoutException as exc:
        kind = "deadline" if deadline is not None and time.monotonic() >= deadline - 1 else {httpx.ConnectTimeout: "connect_timeout", httpx.PoolTimeout: "pool_timeout"}.get(type(exc), "call_timeout")
        raise Timeout(f"{type(exc).__name__} after {timeout:.1f}s", kind, round(timeout, 1)) from exc


def remaining(deadline):
    """시한까지 남은 초(시한이 없으면 None). 이미 지났으면 TimeoutError."""
    if deadline is None:
        return None
    left = deadline - time.monotonic()
    if left <= 0:
        raise Timeout("request deadline exceeded")
    return left


def capped(timeout, deadline):
    """원격 호출 timeout을 남은 시한으로 자른다."""
    left = remaining(deadline)
    return timeout if left is None else min(timeout, left)


@contextmanager
def track():
    """이 블록(과 asyncio.to_thread·``parallel``로 넘긴 작업)의 단계별 시간을 모을 dict."""
    stats = {}
    token = _stats.set(stats)
    try:
        yield stats
    finally:
        _stats.reset(token)


def note(name, value, add=True):
    """``track`` 중이면 단계 값을 남긴다(``add``면 더한다 — 한 요청에서 같은 단계가 여러 번 돈다, ``None``이면 처음 값만)."""
    stats = _stats.get()
    if stats is not None:
        with _lock:
            if add is None:
                stats.setdefault(name, value)
            else:
                stats[name] = stats.get(name, 0) + value if add else value


def tick(name):
    """``track`` 중이면 ``name`` 카운터를 1 올린 새 값(이 요청의 몇 번째인지), 아니면 None."""
    stats = _stats.get()
    if stats is not None:
        with _lock:
            stats[name] = stats.get(name, 0) + 1
            return stats[name]


def keep(name, item, limit=20):
    """``track`` 중이면 ``name`` 목록에 ``item``을 덧붙인다(마지막 ``limit``개만 남긴다) — 실패한 요청의 부분 응답을 남길 때 쓴다."""
    stats = _stats.get()
    if stats is not None:
        with _lock:
            items = stats.setdefault(name, [])
            items.append(item)
            del items[:-limit]

@contextmanager
def timed(name):
    started = time.monotonic()
    try:
        yield
    except BaseException as exc:
        if not hasattr(exc, "docraft_stage"):  # 단계를 요청 집계가 아닌 예외에 붙인다 — 안쪽에서 복구된 예외가 나중의 진짜 실패 stage 를 오염시키지 않는다
            with suppress(AttributeError):  # __slots__ 예외도 원래 오류를 가리지 않는다
                exc.docraft_stage = name.removesuffix("_ms")  # 처음 지나는(가장 안쪽) 단계
        raise
    finally:
        note(name, round((time.monotonic() - started) * 1000))


def parallel(fn, items, workers):
    """``fn(item)``을 최대 ``workers``개 스레드로 돌려 입력 순서대로 돌려준다. 로그 rid·시간 집계를 넘겨준다."""
    items = list(items)
    if len(items) <= 1 or workers <= 1:
        return [fn(item) for item in items]
    with ThreadPoolExecutor(min(workers, len(items))) as pool:
        futures = [pool.submit(contextvars.copy_context().run, fn, item) for item in items]
        return [future.result() for future in futures]


def spawn(fn, *args) -> Future:
    """``fn(*args)``을 지금 시작해 결과를 Future로 돌려준다(로그 rid·시간 집계를 넘긴다). 결과를 쓸지는 호출자가 나중에 정한다."""
    return _background.submit(contextvars.copy_context().run, fn, *args)


def workers():
    """이 서버의 uvicorn 프로세스 수(``WEB_CONCURRENCY``, 기본 1). uvicorn이 같은 변수로 프로세스를 띄운다."""
    return max(1, limit("WEB_CONCURRENCY", 1, 64))


@contextmanager
def _slot(name, default, deadline, stage):
    """``name``(환경변수)이 정한 크기의 서버 공용 자리. 0이면 제한 없음, 시한까지 자리가 안 나면 TimeoutError.
    값은 서버 전체 상한이라 프로세스마다 ``workers()``로 나눈 몫(최소 1)을 쥔다 — 프로세스 수가 상한보다 많으면 넘친다.
    기다린 시간은 ``{stage}_wait_ms``, 자리를 쥔 시간은 ``{stage}_ms``로 남긴다."""
    size = limit(name, default, 256)
    size = size and max(1, size // workers())
    if not size:
        yield
        return
    with _lock:
        gate = _gates.setdefault(name, threading.BoundedSemaphore(size))
    started = time.monotonic()
    acquired = gate.acquire(timeout=remaining(deadline))
    note(f"{stage}_wait_ms", round((time.monotonic() - started) * 1000))
    if not acquired:
        raise Timeout(f"{stage} queue deadline exceeded", "slot_wait")
    try:
        with timed(f"{stage}_ms"):
            yield
    finally:
        gate.release()


def ocr_slot(deadline=None):
    """GPU OCR 호출 자리(``OCR_CONCURRENCY``, 기본 2)."""
    return _slot("OCR_CONCURRENCY", 2, deadline, "ocr")


def provider_slot(deadline=None):
    """VLM provider 호출 자리(``VLM_CONCURRENCY``, 기본 8): 띠·블록 호출이 한꺼번에 몰려 모두 느려지는 대신 줄을 세운다."""
    return _slot("VLM_CONCURRENCY", 8, deadline, "vlm")


def shared(key, compute, deadline=None):
    """``compute()`` 결과를 ``key``로 잠시(``READ_CACHE_TTL_S``, 기본 180초) 기억해 같은 key 요청이 나눠 쓴다.

    같은 key가 계산 중이면 끝나기를 기다려 그 결과를 쓴다(single-flight). 먼저 온 계산이 실패하면 기다리던 쪽이
    다시 계산한다 — 실패는 기억하지 않는다. ``READ_CACHE_SIZE``(기본 8)가 0이면 끈다. 호출자마다 사본을 준다.
    ``cache_hit``은 요청의 첫 호출(페이지 OCR)만 남긴다 — 재처리 크롭 재OCR도 이 경로를 지나 덮어썼다(r9 17쌍 중 6쌍 오기록)."""
    size, ttl = limit("READ_CACHE_SIZE", 8, 1024), limit("READ_CACHE_TTL_S", 180, 3600)
    if not size or not ttl:
        note("cache_hit", False, add=None)
        return compute()
    while True:
        with _lock:
            now = time.monotonic()
            for stale in [k for k, (expires, _) in _cache.items() if expires <= now]:
                del _cache[stale]
            cached = _cache.get(key)
            if cached:
                _cache.move_to_end(key)
            flight = _flights.get(key)
            leader = not cached and flight is None
            if leader:
                flight = _flights[key] = threading.Event()
        if cached:  # 저장된 값은 바뀌지 않고 사본만 나가므로 잠금 밖에서 복사한다
            note("cache_hit", True, add=None)
            return deepcopy(cached[1])
        if leader:
            break
        if not flight.wait(remaining(deadline)):
            raise Timeout("shared read deadline exceeded", "shared_wait")
    try:
        value = compute()
        with _lock:
            _cache[key] = (time.monotonic() + ttl, value)
            while len(_cache) > size:
                _cache.popitem(last=False)
    finally:
        with _lock:
            _flights.pop(key, None)
        flight.set()
    note("cache_hit", False, add=None)
    return deepcopy(value)
