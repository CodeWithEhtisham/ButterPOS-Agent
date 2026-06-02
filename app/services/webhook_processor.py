"""Webhook event processing — V1 stub; agent loop hooks in Phase 2."""

from __future__ import annotations

from app.core.exceptions import WebhookProcessingError
from app.core.logging_config import get_logger
from app.models.standard import StandardEvent, StandardEventType

logger = get_logger("app.webhooks")


async def process_webhook_event(event: StandardEvent) -> None:
    """Handle a normalized webhook event after idempotency gate.

    V1 validates known event types only. Cache invalidation and agent loop
    enqueue arrive in Task 1.5 / Phase 2.
    """
    if event.event_type is StandardEventType.UNKNOWN:
        raise WebhookProcessingError(f"Unsupported webhook event type: {event.event_type.value}")

    logger.info(
        "webhook_processed event_type=%s provider_event_id=%s ticket_id=%s",
        event.event_type.value,
        event.provider_event_id,
        event.provider_ticket_id,
        extra={
            "ticket_id": event.provider_ticket_id,
            "event_type": event.event_type.value,
            "provider_event_id": event.provider_event_id,
            "idempotency_key": event.idempotency_key,
        },
    )


def alert_webhook_dlq_exhausted(
    *,
    idempotency_key: str,
    error_message: str,
    event: StandardEvent,
    attempt_count: int,
) -> None:
    """Structured alert after max DLQ retries — monitor `alert_type=webhook_dlq_exhausted`."""
    logger.error(
        "webhook_dlq_exhausted idempotency_key=%s attempt_count=%s error=%s ticket_id=%s",
        idempotency_key,
        attempt_count,
        error_message,
        event.provider_ticket_id,
        extra={
            "alert_type": "webhook_dlq_exhausted",
            "idempotency_key": idempotency_key,
            "attempt_count": attempt_count,
            "ticket_id": event.provider_ticket_id,
            "event_type": event.event_type.value,
            "provider_event_id": event.provider_event_id,
        },
    )
