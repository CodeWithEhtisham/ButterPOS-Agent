"""Webhook processing dispatch — Celery enqueue with test doubles."""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from app.models.standard import StandardEvent


class WebhookDispatcher(Protocol):
    """Enqueue webhook processing without blocking the HTTP response."""

    def enqueue(self, idempotency_key: str, event: StandardEvent) -> None:
        """Schedule async processing for a newly received webhook."""


class CeleryWebhookDispatcher:
    """Push processing to Celery worker via Redis broker."""

    def enqueue(self, idempotency_key: str, event: StandardEvent) -> None:
        from app.worker.tasks.webhook_tasks import process_webhook_event_task

        process_webhook_event_task.delay(
            idempotency_key,
            event.model_dump(mode="json"),
            1,
        )


class NoOpWebhookDispatcher:
    """Test double — skips Celery (idempotency-only tests)."""

    def enqueue(self, idempotency_key: str, event: StandardEvent) -> None:
        del idempotency_key, event


@lru_cache
def get_webhook_dispatcher() -> WebhookDispatcher:
    return CeleryWebhookDispatcher()


def clear_webhook_dispatcher_cache() -> None:
    get_webhook_dispatcher.cache_clear()
