"""Celery worker: `python -m backend.worker` or `celery -A backend.worker worker -Q $QUEUE_NAME`."""

from . import main  # noqa: F401  registers the parse/extract tasks
from .jobs import CONCURRENCY, QUEUE_NAME, celery_app

app = celery_app()

if __name__ == "__main__":
    app.worker_main(["worker", "-Q", QUEUE_NAME, "-c", str(CONCURRENCY), "--loglevel", "INFO"])
