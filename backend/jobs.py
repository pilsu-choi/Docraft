"""Job dispatch: `enqueue(name, *args)` hands a registered task to the backend chosen by QUEUE_BACKEND.

Backends take `(name, args)`. Add one by writing that function and registering it in BACKENDS.
Tasks must be idempotent-ish: they claim their document with a conditional DB update before working.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import cache

logger = logging.getLogger(__name__)

TASKS = {}
QUEUE_NAME = os.getenv("QUEUE_NAME", "docraft")
CONCURRENCY = int(os.getenv("QUEUE_CONCURRENCY", "2"))
# A running job heartbeats every LEASE/3 seconds; one silent for LEASE seconds is taken over.
LEASE = int(os.getenv("JOB_LEASE_SECONDS", "600"))


def task(name):
    """Register a function as the task `name` (backend.main registers `parse` and `extract`)."""
    def register(fn):
        TASKS[name] = fn
        return fn
    return register


def enqueue(name, *args):
    backend()(name, args)


def backend():
    selected = os.getenv("QUEUE_BACKEND", "inline")
    if selected not in BACKENDS:
        raise RuntimeError(f"QUEUE_BACKEND={selected!r} is not one of {sorted(BACKENDS)}")
    return BACKENDS[selected]


_pool = ThreadPoolExecutor(max_workers=CONCURRENCY, thread_name_prefix="docraft-job")


def _inline(name, args):
    def run():
        try: TASKS[name](*args)
        except Exception: logger.exception("job failed: %s%s", name, args)
    _pool.submit(run)


def _celery(name, args):
    celery_app().send_task(f"{QUEUE_NAME}.{name}", args=args, queue=QUEUE_NAME)


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
