"""Celery application — broker on Redis, beat for DLQ retries."""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "butterpos_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks.webhook_tasks", "app.worker.tasks.polling_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.celery_timezone,
    enable_utc=True,
    task_track_started=True,
)

celery_app.conf.beat_schedule = {
    "retry-webhook-dlq": {
        "task": "webhook.retry_dlq",
        "schedule": float(settings.webhook_dlq_retry_interval_seconds),
    },
    "poll-ticket-reconcile": {
        "task": "ticket.poll_reconcile",
        "schedule": float(settings.webhook_polling_interval_seconds),
    },
}
