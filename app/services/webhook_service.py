"""Inbound webhook business logic — verify, parse, idempotency, dispatch, and acknowledge."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dedup.webhook import WebhookHotDedupStore, get_webhook_hot_dedup_store
from app.core.exceptions import RateLimitExceededError, WebhookVerificationError
from app.core.logging_config import get_logger
from app.core.rate_limit.inbound_message_limits import (
    InboundMessageRateLimiter,
    get_inbound_message_rate_limiter,
)
from app.models.standard import StandardEvent
from app.providers.ticketing.base import TicketingProvider
from app.repositories.webhook_event_repository import (
    compute_payload_hash,
    mark_webhook_failed,
    record_webhook_event,
)
from app.schemas.webhook_dlq import WebhookDlqPayload
from app.services.webhook_dispatch import WebhookDispatcher, get_webhook_dispatcher
from app.worker.dlq import InMemoryWebhookDlqStore, WebhookDlqStore, get_webhook_dlq_store

logger = get_logger("app.webhooks")

WebhookReceiveStatus = Literal["accepted", "duplicate", "rate_limited"]


@dataclass(frozen=True)
class WebhookReceiveResult:
    """Full outcome of inbound webhook handling through idempotency gate."""

    event: StandardEvent
    status: WebhookReceiveStatus
    idempotency_key: str
    payload_hash: str


class WebhookService:
    """Receive platform webhooks via TicketingProvider adapter."""

    def __init__(
        self,
        provider: TicketingProvider,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        dispatcher: WebhookDispatcher | None = None,
        dlq_store: WebhookDlqStore | InMemoryWebhookDlqStore | None = None,
        rate_limiter: InboundMessageRateLimiter | None = None,
        hot_dedup: WebhookHotDedupStore | None = None,
    ) -> None:
        self._provider = provider
        self._session = session
        self._settings = settings or get_settings()
        self._dispatcher = dispatcher if dispatcher is not None else get_webhook_dispatcher()
        self._dlq_store = dlq_store
        self._rate_limiter = rate_limiter if rate_limiter is not None else get_inbound_message_rate_limiter()
        self._hot_dedup = hot_dedup if hot_dedup is not None else get_webhook_hot_dedup_store()

    def _get_dlq_store(self) -> WebhookDlqStore | InMemoryWebhookDlqStore:
        if self._dlq_store is None:
            self._dlq_store = get_webhook_dlq_store()
        return self._dlq_store

    async def receive_chatwoot(self, raw_body: bytes, headers: dict[str, str]) -> WebhookReceiveResult:
        """Verify HMAC, parse payload, persist idempotency record, enqueue processing."""
        if not await self._provider.verify_webhook(raw_body, headers):
            raise WebhookVerificationError()

        event = await self._provider.parse_webhook(raw_body, headers)
        payload_hash = compute_payload_hash(raw_body)

        if event.idempotency_key and await self._hot_dedup.is_duplicate(event.idempotency_key):
            logger.info(
                "webhook_hot_dedup_duplicate idempotency_key=%s ticket_id=%s",
                event.idempotency_key,
                event.provider_ticket_id,
                extra={"idempotency_key": event.idempotency_key, "ticket_id": event.provider_ticket_id},
            )
            return WebhookReceiveResult(
                event=event,
                status="duplicate",
                idempotency_key=event.idempotency_key,
                payload_hash=payload_hash,
            )

        record = await record_webhook_event(self._session, event=event, raw_body=raw_body)

        status: WebhookReceiveStatus = "duplicate" if record.status == "duplicate" else "accepted"
        if record.status == "received":
            await self._hot_dedup.remember(record.idempotency_key)
            try:
                await self._rate_limiter.check(event)
            except RateLimitExceededError as exc:
                await mark_webhook_failed(self._session, record.idempotency_key, exc.message)
                status = "rate_limited"
                logger.warning(
                    "webhook_rate_limited idempotency_key=%s ticket_id=%s",
                    record.idempotency_key,
                    event.provider_ticket_id,
                    extra={
                        "idempotency_key": record.idempotency_key,
                        "ticket_id": event.provider_ticket_id,
                    },
                )
            else:
                await self._enqueue_processing(record.idempotency_key, event)

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

    async def _enqueue_processing(self, idempotency_key: str, event: StandardEvent) -> None:
        try:
            await asyncio.to_thread(self._dispatcher.enqueue, idempotency_key, event)
        except Exception as exc:
            error_message = f"Celery dispatch failed: {exc}"
            logger.exception(
                "webhook_dispatch_failed idempotency_key=%s",
                idempotency_key,
                extra={"idempotency_key": idempotency_key, "ticket_id": event.provider_ticket_id},
            )
            await mark_webhook_failed(self._session, idempotency_key, error_message)
            await asyncio.to_thread(
                self._get_dlq_store().enqueue,
                WebhookDlqPayload(
                    idempotency_key=idempotency_key,
                    attempt_count=1,
                    error_message=error_message,
                    event=event.model_dump(mode="json"),
                    next_retry_at=time.time() + self._settings.webhook_dlq_retry_interval_seconds,
                ),
            )
