"""Inbound webhook business logic — verify, parse, and acknowledge."""

from __future__ import annotations

from app.core.exceptions import WebhookVerificationError
from app.core.logging_config import get_logger
from app.models.standard import StandardEvent
from app.providers.ticketing.base import TicketingProvider

logger = get_logger("app.webhooks")


class WebhookService:
    """Receive platform webhooks via TicketingProvider adapter."""

    def __init__(self, provider: TicketingProvider) -> None:
        self._provider = provider

    async def receive_chatwoot(self, raw_body: bytes, headers: dict[str, str]) -> StandardEvent:
        """Verify HMAC, parse payload to StandardEvent, log for audit."""
        if not await self._provider.verify_webhook(raw_body, headers):
            raise WebhookVerificationError()

        event = await self._provider.parse_webhook(raw_body, headers)
        logger.info(
            "webhook_received provider=%s event_type=%s provider_event_id=%s ticket_id=%s",
            self._provider.provider_name,
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
        return event
