"""Celery tasks for webhook processing and DLQ retries — Task 1.4.3."""

from __future__ import annotations

import asyncio
import time

from app.core.config import get_settings
from app.core.exceptions import WebhookProcessingError
from app.core.logging_config import get_logger
from app.db.session import get_session_factory, init_engine, shutdown_engine
from app.models.standard import StandardEvent
from app.repositories.webhook_event_repository import mark_webhook_failed, mark_webhook_processed
from app.schemas.webhook_dlq import WebhookDlqPayload
from app.services.webhook_processor import alert_webhook_dlq_exhausted, process_webhook_event
from app.worker.celery_app import celery_app
from app.worker.dlq import InMemoryWebhookDlqStore, WebhookDlqStore, build_webhook_dlq_store

logger = get_logger("app.webhooks.worker")


async def _handle_webhook_failure(
    *,
    idempotency_key: str,
    event: StandardEvent,
    attempt: int,
    error_message: str,
    dlq_store: WebhookDlqStore | None = None,
) -> None:
    settings = get_settings()
    store = dlq_store or build_webhook_dlq_store(settings)

    init_engine(settings)
    factory = get_session_factory()
    async with factory() as session:
        await mark_webhook_failed(session, idempotency_key, error_message)
        await session.commit()

    if attempt >= settings.webhook_dlq_max_attempts:
        alert_webhook_dlq_exhausted(
            idempotency_key=idempotency_key,
            error_message=error_message,
            event=event,
            attempt_count=attempt,
        )
        return

    next_attempt = attempt + 1
    store.enqueue(
        WebhookDlqPayload(
            idempotency_key=idempotency_key,
            attempt_count=next_attempt,
            error_message=error_message,
            event=event.model_dump(mode="json"),
            next_retry_at=time.time() + settings.webhook_dlq_retry_interval_seconds,
        )
    )
    logger.warning(
        "webhook_enqueued_dlq idempotency_key=%s next_attempt=%s error=%s",
        idempotency_key,
        next_attempt,
        error_message,
        extra={"idempotency_key": idempotency_key, "ticket_id": event.provider_ticket_id},
    )


async def _process_webhook_event_async(
    idempotency_key: str,
    event_data: dict,
    attempt: int,
) -> None:
    settings = get_settings()
    event = StandardEvent.model_validate(event_data)

    init_engine(settings)
    factory = get_session_factory()
    try:
        async with factory() as session:
            await process_webhook_event(event, db=session, settings=settings)
            await mark_webhook_processed(session, idempotency_key)
            await session.commit()
    except WebhookProcessingError as exc:
        await _handle_webhook_failure(
            idempotency_key=idempotency_key,
            event=event,
            attempt=attempt,
            error_message=str(exc),
        )
    finally:
        await shutdown_engine()


@celery_app.task(name="webhook.process")
def process_webhook_event_task(idempotency_key: str, event_data: dict, attempt: int = 1) -> None:
    """Process one webhook event — success marks processed, failure routes to DLQ."""
    asyncio.run(_process_webhook_event_async(idempotency_key, event_data, attempt))


@celery_app.task(name="webhook.retry_dlq")
def retry_webhook_dlq_task() -> int:
    """Beat task — drain ready DLQ entries and re-dispatch processing."""
    settings = get_settings()
    dlq_store = build_webhook_dlq_store(settings)
    dispatched = 0
    for entry in dlq_store.pop_ready():
        process_webhook_event_task.delay(
            entry.idempotency_key,
            entry.event,
            entry.attempt_count,
        )
        dispatched += 1
    if dispatched:
        logger.info("webhook_dlq_retry_dispatched count=%s", dispatched)
    return dispatched
