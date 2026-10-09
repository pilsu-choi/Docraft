"""요청 지연을 줄이는 프로세스 공용 장치: 같은 페이지 결과 공유, GPU OCR·VLM 동시성 제한, 병렬 호출, 단계별 시간 집계.

하네스는 같은 페이지의 필드 요청과 표 요청을 동시에 보낸다. ``shared``는 그 둘이 OCR·표 교정을 한 번만 하게 하고,
``ocr_slot``·``provider_slot``은 포화된 GPU에 요청이 몰려 모두 느려지는 대신 줄을 세운다. ``track``으로 묶은 요청은 ``timed``·
``ocr_slot``·``shared``가 남긴 단계별 시간을 한 dict로 모은다(``read finished`` 로그 줄).
"""

import contextvars
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy

from .config import limit

_stats: contextvars.ContextVar[dict | None] = contextvars.ContextVar("docraft_stats", default=None)
_lock = threading.Lock()
_cache: OrderedDict = OrderedDict()  # key -> (만료 시각, 값)
_flights: dict = {}  # 계산 중인 key -> 끝나면 세워지는 Event
_gates: dict[str, threading.BoundedSemaphore] = {}  # 환경변수 이름 -> 자리(첫 호출 때 크기 고정)


def remaining(deadline):
    """시한까지 남은 초(시한이 없으면 None). 이미 지났으면 TimeoutError."""
    if deadline is None:
        return None
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError("request deadline exceeded")
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


@contextmanager
def timed(name):
    started = time.monotonic()
    try:
        yield
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


@contextmanager
def _slot(name, default, deadline, stage):
    """``name``(환경변수)이 정한 크기의 프로세스 공용 자리. 0이면 제한 없음, 시한까지 자리가 안 나면 TimeoutError.
    기다린 시간은 ``{stage}_wait_ms``, 자리를 쥔 시간은 ``{stage}_ms``로 남긴다."""
    size = limit(name, default, 256)
    if not size:
        yield
        return
    with _lock:
        gate = _gates.setdefault(name, threading.BoundedSemaphore(size))
    started = time.monotonic()
    acquired = gate.acquire(timeout=remaining(deadline))
    note(f"{stage}_wait_ms", round((time.monotonic() - started) * 1000))
    if not acquired:
        raise TimeoutError(f"{stage} queue deadline exceeded")
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
            raise TimeoutError("shared read deadline exceeded")
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
