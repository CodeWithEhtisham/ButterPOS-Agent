"""DLQ retry task — runs every 5 min."""

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.webhook_retry.retry_failed_webhooks")
def retry_failed_webhooks():
    """Retry failed webhook events from the dead letter queue."""
    pass
