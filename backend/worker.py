"""Celery worker: `python -m backend.worker` or `celery -A backend.worker worker -Q $QUEUE_NAME`."""

from . import main  # noqa: F401  registers the parse/extract tasks
from . import master
from .jobs import CONCURRENCY, QUEUE_NAME, celery_app

master.ready()  # 첫 작업 전에 마스터 사전 캐시를 미리 채운다
app = celery_app()

if __name__ == "__main__":
    app.worker_main(["worker", "-Q", QUEUE_NAME, "-c", str(CONCURRENCY), "--loglevel", "INFO"])
