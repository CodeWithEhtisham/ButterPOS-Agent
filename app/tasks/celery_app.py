"""Celery application configuration."""

from celery import Celery
from app.config import settings

celery_app = Celery(
    "butterpos",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "check-sla-timers": {
        "task": "app.tasks.sla_tasks.check_sla_timers",
        "schedule": 60.0,  # every 60 seconds
    },
    "retry-dead-webhooks": {
        "task": "app.tasks.webhook_retry.retry_failed_webhooks",
        "schedule": 300.0,  # every 5 minutes
    },
    "poll-ticket-sync": {
        "task": "app.tasks.polling_fallback.sync_tickets",
        "schedule": 600.0,  # every 10 minutes
    },
    "check-circuit-breaker": {
        "task": "app.tasks.circuit_breaker.check_ai_health",
        "schedule": 300.0,  # every 5 minutes
    },
}

celery_app.autodiscover_tasks([
    "app.tasks.sla_tasks",
    "app.tasks.webhook_retry",
    "app.tasks.report_tasks",
    "app.tasks.csat_analysis",
    "app.tasks.polling_fallback",
    "app.tasks.circuit_breaker",
])
