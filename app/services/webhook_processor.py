"""Webhook event processing — cache invalidation + inbound agent loop (Phase 2.1.2)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.ticketing_read_cache import get_ticketing_read_cache
from app.core.config import Settings, get_settings
from app.core.exceptions import WebhookProcessingError
from app.core.logging_config import get_logger
from app.models.standard import StandardEvent, StandardEventType
from app.providers.ticketing.factory import create_ticketing_provider
from app.services.agent_factory import build_agent_service
from app.services.chat_relay_service import ChatRelayService
from app.services.inbound_agent_service import InboundAgentService
from app.services.inbound_pii_service import InboundPiiService, get_inbound_pii_service

logger = get_logger("app.webhooks")


async def process_webhook_event(
    event: StandardEvent,
    *,
    db: AsyncSession | None = None,
    settings: Settings | None = None,
    pii_service: InboundPiiService | None = None,
    inbound_agent: InboundAgentService | None = None,
) -> None:
    """Handle a normalized webhook event after idempotency gate.

    V1 validates known event types, masks inbound PII in message bodies (Redis token
    map), invalidates Redis read caches, and runs the inbound agent on customer
    message_created events when ``AGENT_INBOUND_ENABLED`` is true.
    """
    if event.event_type is StandardEventType.UNKNOWN:
        raise WebhookProcessingError(f"Unsupported webhook event type: {event.event_type.value}")

    app_settings = settings or get_settings()
    service = pii_service if pii_service is not None else get_inbound_pii_service()
    event = await service.mask_event_for_processing(event)

    await get_ticketing_read_cache().invalidate_for_webhook(
        provider_ticket_id=event.provider_ticket_id,
        sender_provider_contact_id=event.sender_provider_contact_id,
    )

    agent_ran = False
    relayed = False
    if db is not None:
        relay = ChatRelayService()
        relayed = await relay.relay_outgoing_to_widget(db, event)

    if db is not None and app_settings.agent_inbound_enabled:
        agent_service = inbound_agent
        if agent_service is None:
            ticketing = create_ticketing_provider(app_settings)
            agent = await build_agent_service(app_settings)
            agent_service = InboundAgentService(app_settings, agent, ticketing)
        try:
            agent_ran = await agent_service.handle_event(db, event)
        except RuntimeError as exc:
            raise WebhookProcessingError(str(exc)) from exc

    logger.info(
        "webhook_processed event_type=%s provider_event_id=%s ticket_id=%s agent_ran=%s relayed=%s",
        event.event_type.value,
        event.provider_event_id,
        event.provider_ticket_id,
        agent_ran,
        relayed,
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
