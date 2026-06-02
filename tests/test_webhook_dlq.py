"""Webhook DLQ and Celery processing tests — Task 1.4 sub-step 3."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.config import Settings, get_settings
from app.core.dedup.store import InMemoryDedupStore
from app.core.dedup.webhook import WebhookHotDedupStore
from app.core.exceptions import WebhookProcessingError
from app.models.standard import StandardEvent, StandardEventType
from app.repositories.webhook_event_repository import mark_webhook_failed, mark_webhook_processed
from app.schemas.webhook_dlq import WebhookDlqPayload
from app.services.webhook_dispatch import NoOpWebhookDispatcher
from app.services.webhook_processor import process_webhook_event
from app.services.webhook_service import WebhookService
from app.worker.dlq import InMemoryWebhookDlqStore
from app.worker.tasks import webhook_tasks
from tests.support.idempotency_memory_session import IdempotencyMemorySession


def _event(*, key: str = "message_created:1") -> StandardEvent:
    return StandardEvent(
        event_type=StandardEventType.MESSAGE_CREATED,
        provider_event_id="1",
        provider_ticket_id="5678",
        occurred_at=datetime.now(tz=UTC),
        idempotency_key=key,
    )


def test_in_memory_dlq_respects_next_retry_at() -> None:
    store = InMemoryWebhookDlqStore()
    future = WebhookDlqPayload(
        idempotency_key="k1",
        attempt_count=2,
        error_message="fail",
        event=_event().model_dump(mode="json"),
        next_retry_at=time.time() + 3600,
    )
    store.enqueue(future)
    assert store.pop_ready() == []

    past = future.model_copy(update={"next_retry_at": time.time() - 1})
    store.enqueue(past)
    ready = store.pop_ready()
    assert len(ready) == 1
    assert ready[0].idempotency_key == "k1"


def test_process_webhook_event_rejects_unknown_type() -> None:
    unknown = _event().model_copy(
        update={"event_type": StandardEventType.UNKNOWN},
    )

    async def _run() -> None:
        with pytest.raises(WebhookProcessingError, match="Unsupported"):
            await process_webhook_event(unknown)

    asyncio.run(_run())


def test_process_webhook_event_accepts_message_created() -> None:
    async def _run() -> None:
        from app.core.cache.json_blob_cache import InMemoryJsonBlobCache
        from app.core.cache.ticketing_read_cache import build_ticketing_read_cache

        read_cache = build_ticketing_read_cache(
            Settings(_env_file=None),
            blob_cache=InMemoryJsonBlobCache(),
        )
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.webhook_processor.get_ticketing_read_cache",
                lambda: read_cache,
            )
            from app.core.pii.detector import RegexPiiDetector
            from app.core.pii.masker import PIIMasker
            from app.core.pii.store import InMemoryPiiTokenStore
            from app.services.inbound_pii_service import InboundPiiService

            pii = InboundPiiService(PIIMasker(InMemoryPiiTokenStore(), RegexPiiDetector()))
            await process_webhook_event(_event(), pii_service=pii)

    asyncio.run(_run())


def test_mark_webhook_processed_and_failed() -> None:
    async def _run() -> None:
        session = IdempotencyMemorySession()
        from app.repositories.webhook_event_repository import record_webhook_event

        body = b'{"event":"message_created","id":1}'
        await record_webhook_event(session, event=_event(), raw_body=body)
        await mark_webhook_failed(session, "message_created:1", "boom")
        row = session._rows["message_created:1"]
        assert row.status == "failed"
        assert row.error_message == "boom"

        await mark_webhook_processed(session, "message_created:1")
        row = session._rows["message_created:1"]
        assert row.status == "processed"
        assert row.processed_at is not None

    asyncio.run(_run())


def test_webhook_service_falls_back_to_dlq_on_dispatch_failure() -> None:
    class FailingDispatcher:
        def enqueue(self, idempotency_key: str, event: StandardEvent) -> None:
            del idempotency_key, event
            raise ConnectionError("broker down")

    async def _run() -> None:
        provider = MagicMock()
        provider.provider_name = "chatwoot"
        provider.verify_webhook = AsyncMock(return_value=True)
        provider.parse_webhook = AsyncMock(return_value=_event())

        session = IdempotencyMemorySession()
        dlq = InMemoryWebhookDlqStore()
        settings = Settings(
            _env_file=None,
            webhook_dlq_retry_interval_seconds=300,
        )
        service = WebhookService(
            provider,
            session,
            settings=settings,
            dispatcher=FailingDispatcher(),
            dlq_store=dlq,
            hot_dedup=WebhookHotDedupStore(InMemoryDedupStore(), ttl_seconds=3600),
            rate_limiter=MagicMock(check=AsyncMock()),
        )
        result = await service.receive_chatwoot(b"{}", {})
        assert result.status == "accepted"
        assert session._rows["message_created:1"].status == "failed"
        ready = dlq.pop_ready()
        assert len(ready) == 0
        # next_retry_at is in the future
        assert len(dlq._items) == 1

    asyncio.run(_run())


def test_handle_failure_enqueues_dlq_before_max_attempts() -> None:
    settings = Settings(_env_file=None, webhook_dlq_max_attempts=3, webhook_dlq_retry_interval_seconds=300)
    dlq = InMemoryWebhookDlqStore()

    async def _run() -> None:
        with patch.object(webhook_tasks, "get_settings", return_value=settings):
            with patch.object(webhook_tasks, "init_engine"):
                with patch.object(webhook_tasks, "mark_webhook_failed", new_callable=AsyncMock) as mark_mock:
                    await webhook_tasks._handle_webhook_failure(
                        idempotency_key="message_created:1",
                        event=_event(),
                        attempt=1,
                        error_message="processing failed",
                        dlq_store=dlq,
                    )
                    mark_mock.assert_awaited_once()

    asyncio.run(_run())
    assert len(dlq._items) == 1
    assert dlq._items[0][1].attempt_count == 2


def test_handle_failure_alerts_after_max_attempts() -> None:
    settings = Settings(_env_file=None, webhook_dlq_max_attempts=3)
    dlq = InMemoryWebhookDlqStore()

    async def _run() -> None:
        session = IdempotencyMemorySession()
        with patch.object(webhook_tasks, "get_settings", return_value=settings):
            with patch.object(webhook_tasks, "init_engine"):
                with patch.object(webhook_tasks, "get_session_factory") as factory_mock:
                    factory_mock.return_value = MagicMock(
                        __aenter__=AsyncMock(return_value=session),
                        __aexit__=AsyncMock(return_value=False),
                    )
                    with patch.object(webhook_tasks, "alert_webhook_dlq_exhausted") as alert_mock:
                        await webhook_tasks._handle_webhook_failure(
                            idempotency_key="message_created:1",
                            event=_event(),
                            attempt=3,
                            error_message="still failing",
                            dlq_store=dlq,
                        )
                        alert_mock.assert_called_once()
        assert dlq._items == []

    asyncio.run(_run())


def test_retry_dlq_task_dispatches_ready_entries() -> None:
    dlq = InMemoryWebhookDlqStore()
    dlq.enqueue(
        WebhookDlqPayload(
            idempotency_key="message_created:1",
            attempt_count=2,
            error_message="retry",
            event=_event().model_dump(mode="json"),
            next_retry_at=time.time() - 1,
        )
    )
    settings = Settings(_env_file=None)
    with patch.object(webhook_tasks, "build_webhook_dlq_store", return_value=dlq):
        with patch.object(webhook_tasks, "get_settings", return_value=settings):
            with patch.object(webhook_tasks, "process_webhook_event_task") as task_mock:
                count = webhook_tasks.retry_webhook_dlq_task()
                assert count == 1
                task_mock.delay.assert_called_once()
                call_args = task_mock.delay.call_args[0]
                assert call_args[0] == "message_created:1"
                assert call_args[2] == 2
