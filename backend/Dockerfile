# Build context: repo root (docker compose sets `context: .`).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# The image serves both the API and the queue worker, so it includes the optional celery extra.
COPY requirements.txt requirements-queue.txt ./
RUN pip install --no-cache-dir -r requirements-queue.txt

COPY backend ./backend

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
