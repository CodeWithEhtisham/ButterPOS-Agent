"""Inbound webhook business logic — verify, parse, idempotency, and acknowledge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import WebhookVerificationError
from app.core.logging_config import get_logger
from app.models.standard import StandardEvent
from app.providers.ticketing.base import TicketingProvider
from app.repositories.webhook_event_repository import WebhookRecordResult, record_webhook_event

logger = get_logger("app.webhooks")

WebhookReceiveStatus = Literal["accepted", "duplicate"]


@dataclass(frozen=True)
class WebhookReceiveResult:
    """Full outcome of inbound webhook handling through idempotency gate."""

    event: StandardEvent
    status: WebhookReceiveStatus
    idempotency_key: str
    payload_hash: str


class WebhookService:
    """Receive platform webhooks via TicketingProvider adapter."""

    def __init__(self, provider: TicketingProvider, session: AsyncSession) -> None:
        self._provider = provider
        self._session = session

    async def receive_chatwoot(self, raw_body: bytes, headers: dict[str, str]) -> WebhookReceiveResult:
        """Verify HMAC, parse payload, persist idempotency record, return outcome."""
        if not await self._provider.verify_webhook(raw_body, headers):
            raise WebhookVerificationError()

        event = await self._provider.parse_webhook(raw_body, headers)
        record = await record_webhook_event(self._session, event=event, raw_body=raw_body)

        status: WebhookReceiveStatus = "duplicate" if record.status == "duplicate" else "accepted"
        logger.info(
            "webhook_received provider=%s event_type=%s provider_event_id=%s ticket_id=%s status=%s",
            self._provider.provider_name,
            event.event_type.value,
            event.provider_event_id,
            event.provider_ticket_id,
            status,
            extra={
                "ticket_id": event.provider_ticket_id,
                "event_type": event.event_type.value,
                "provider_event_id": event.provider_event_id,
                "idempotency_key": record.idempotency_key,
                "payload_hash": record.payload_hash,
            },
        )
        return WebhookReceiveResult(
            event=event,
            status=status,
            idempotency_key=record.idempotency_key,
            payload_hash=record.payload_hash,
        )
