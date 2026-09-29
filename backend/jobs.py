"""Job dispatch: `enqueue(name, *args)` hands a registered task to the backend chosen by QUEUE_BACKEND.

Backends take `(name, args, rid)`. Add one by writing that function and registering it in BACKENDS.
Tasks must be idempotent-ish: they claim their document with a conditional DB update before working.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import cache, wraps

from .config import bind_request, request_id

logger = logging.getLogger(__name__)

TASKS = {}
QUEUE_NAME = os.getenv("QUEUE_NAME", "docraft")
CONCURRENCY = int(os.getenv("QUEUE_CONCURRENCY", "2"))
# A running job heartbeats every LEASE/3 seconds; one silent for LEASE seconds is taken over.
LEASE = int(os.getenv("JOB_LEASE_SECONDS", "600"))


def task(name):
    """Register a function as the task `name` (backend.main registers `parse` and `extract`).

    작업 안의 로그 줄에는 `[<요청 rid>><parse>:<document_id>]` 처럼 enqueue 한 요청의 rid, 작업 이름, 첫 인자가 붙는다(inline·celery 공통).
    rid 가 없는 옛 메시지는 `[parse:<document_id>]`.
    """
    def register(fn):
        @wraps(fn)
        def run(*args, rid=None):
            with bind_request(f"{rid}>" * bool(rid) + (f"{name}:{args[0]}" if args else name)):
                return fn(*args)
        TASKS[name] = run
        return run
    return register


def enqueue(name, *args):
    """작업을 큐에 넣고 백엔드의 결과(Celery면 AsyncResult, inline이면 Future)를 돌려준다 — 호출자가 취소용 id를 챙길 수 있게."""
    return backend()(name, args, request_id())


def revoke(task_id):
    """Celery 모드에서 아직 시작하지 않은 작업을 브로커 큐에서 뺀다(최선 노력). 이미 실행 중인 작업은
    documents.cancel_requested를 다음 단계 경계에서 확인해 스스로 멈춘다(backend/main.py의 check_cancel).
    """
    if task_id and os.getenv("QUEUE_BACKEND", "inline") == "celery":
        celery_app().control.revoke(task_id)


def backend():
    selected = os.getenv("QUEUE_BACKEND", "inline")
    if selected not in BACKENDS:
        raise RuntimeError(f"QUEUE_BACKEND={selected!r} is not one of {sorted(BACKENDS)}")
    return BACKENDS[selected]


_pool = ThreadPoolExecutor(max_workers=CONCURRENCY, thread_name_prefix="docraft-job")


def _inline(name, args, rid):
    def run():
        try: TASKS[name](*args, rid=rid if rid != "-" else None)
        except Exception: logger.exception("job failed: %s%s", name, args)
    return _pool.submit(run)


def _celery(name, args, rid):
    return celery_app().send_task(f"{QUEUE_NAME}.{name}", args=args, kwargs={"rid": rid} if rid != "-" else {}, queue=QUEUE_NAME)


BACKENDS = {"inline": _inline, "celery": _celery}


@cache
def celery_app():
    """Celery app whose queue, task names and redis keys are all namespaced by QUEUE_NAME for shared infra."""
    import psycopg
    from celery import Celery

    broker = os.environ["CELERY_BROKER_URL"]
    app = Celery(QUEUE_NAME, broker=broker, backend=os.getenv("CELERY_RESULT_BACKEND") or None)
    prefix = {"global_keyprefix": f"{QUEUE_NAME}:"} if broker.startswith(("redis://", "rediss://")) else {}
    app.conf.update(
        task_serializer="json", accept_content=["json"], task_ignore_result=True,
        task_default_queue=QUEUE_NAME, task_acks_late=True, task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1, broker_connection_retry_on_startup=True,
        # Redis redelivers an unacked message after visibility_timeout; match the lease so a dead worker's job resumes soon.
        broker_transport_options={**prefix, "visibility_timeout": LEASE}, result_backend_transport_options=prefix,
    )
    for name, fn in TASKS.items():
        app.task(name=f"{QUEUE_NAME}.{name}", autoretry_for=(psycopg.OperationalError, OSError),
                 retry_backoff=True, max_retries=3)(fn)
    return app
