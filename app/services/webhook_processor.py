"""Webhook event processing — V1 stub; agent loop hooks in Phase 2."""

from __future__ import annotations

from app.core.cache.ticketing_read_cache import get_ticketing_read_cache
from app.core.exceptions import WebhookProcessingError
from app.core.logging_config import get_logger
from app.models.standard import StandardEvent, StandardEventType
from app.services.inbound_pii_service import InboundPiiService, get_inbound_pii_service

logger = get_logger("app.webhooks")


async def process_webhook_event(
    event: StandardEvent,
    *,
    pii_service: InboundPiiService | None = None,
) -> None:
    """Handle a normalized webhook event after idempotency gate.

    V1 validates known event types, masks inbound PII in message bodies (Redis token
    map), and invalidates Redis read caches so the next get_ticket /
    get_or_create_contact fetches fresh platform data.
    """
    if event.event_type is StandardEventType.UNKNOWN:
        raise WebhookProcessingError(f"Unsupported webhook event type: {event.event_type.value}")

    service = pii_service if pii_service is not None else get_inbound_pii_service()
    event = await service.mask_event_for_processing(event)

    await get_ticketing_read_cache().invalidate_for_webhook(
        provider_ticket_id=event.provider_ticket_id,
        sender_provider_contact_id=event.sender_provider_contact_id,
    )

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
