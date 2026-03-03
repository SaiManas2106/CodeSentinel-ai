"""Celery app configuration."""

from __future__ import annotations

from celery import Celery

from backend.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "codesentinel",
    broker=settings.redis.url,
    backend=settings.redis.url,
    include=["backend.workers.review_worker", "backend.workers.ingestion_worker"],
)

celery_app.conf.update(
    task_default_queue="reviews",
    task_routes={
        "backend.workers.review_worker.*": {"queue": "reviews"},
        "backend.workers.ingestion_worker.*": {"queue": "ingestion"},
        "backend.workers.notifications.*": {"queue": "notifications"},
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_default_retry_delay=60,
    task_annotations={"*": {"max_retries": 3}},
    timezone="UTC",
    beat_schedule={
        "cleanup-old-metrics": {
            "task": "backend.workers.ingestion_worker.cleanup_progress",
            "schedule": 3600.0,
        }
    },
)
