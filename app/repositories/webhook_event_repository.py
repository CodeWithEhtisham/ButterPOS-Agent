"""Webhook event log persistence — idempotency and payload audit."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging_config import get_logger
from app.db.models.webhook_event_log import WebhookEventLog
from app.models.standard import StandardEvent

logger = get_logger("app.webhooks")

WebhookRecordStatus = Literal["received", "duplicate"]


@dataclass(frozen=True)
class WebhookRecordResult:
    """Outcome of idempotency insert — received is new, duplicate is a replay."""

    status: WebhookRecordStatus
    idempotency_key: str
    payload_hash: str


def compute_payload_hash(raw_body: bytes) -> str:
    """SHA-256 hex digest of raw webhook body for audit and mismatch detection."""
    return hashlib.sha256(raw_body).hexdigest()


async def record_webhook_event(
    session: AsyncSession,
    *,
    event: StandardEvent,
    raw_body: bytes,
) -> WebhookRecordResult:
    """Insert webhook audit row; return duplicate without raising on replay."""
    if not event.idempotency_key:
        raise AppError("Webhook event missing idempotency_key", status_code=400)

    payload_hash = compute_payload_hash(raw_body)
    key = event.idempotency_key

    row = WebhookEventLog(
        idempotency_key=key,
        payload_hash=payload_hash,
        event_type=event.event_type.value,
        provider_event_id=event.provider_event_id,
        provider_ticket_id=event.provider_ticket_id,
        status="received",
        occurred_at=event.occurred_at,
    )

    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            select(WebhookEventLog).where(WebhookEventLog.idempotency_key == key)
        )
        if existing is not None and existing.payload_hash != payload_hash:
            logger.warning(
                "webhook_duplicate_hash_mismatch idempotency_key=%s stored_hash=%s incoming_hash=%s",
                key,
                existing.payload_hash,
                payload_hash,
                extra={"idempotency_key": key, "ticket_id": event.provider_ticket_id},
            )
        logger.info(
            "webhook_duplicate idempotency_key=%s ticket_id=%s",
            key,
            event.provider_ticket_id,
            extra={"idempotency_key": key, "ticket_id": event.provider_ticket_id},
        )
        return WebhookRecordResult(status="duplicate", idempotency_key=key, payload_hash=payload_hash)

    logger.info(
        "webhook_recorded idempotency_key=%s payload_hash=%s ticket_id=%s",
        key,
        payload_hash,
        event.provider_ticket_id,
        extra={
            "idempotency_key": key,
            "payload_hash": payload_hash,
            "ticket_id": event.provider_ticket_id,
        },
    )
    return WebhookRecordResult(status="received", idempotency_key=key, payload_hash=payload_hash)
