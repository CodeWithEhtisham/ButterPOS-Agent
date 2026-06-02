"""Celery tasks for ticket polling fallback — Task 1.4.4."""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.db.session import get_session_factory, init_engine, shutdown_engine
from app.providers.ticketing.factory import create_ticketing_provider
from app.services.ticket_polling_service import TicketPollingService
from app.worker.celery_app import celery_app

logger = get_logger("app.polling.worker")


async def _poll_reconcile_async() -> dict[str, int | str]:
    settings = get_settings()
    init_engine(settings)
    provider = create_ticketing_provider(settings)
    factory = get_session_factory()
    try:
        async with factory() as session:
            result = await TicketPollingService(provider, session, settings=settings).reconcile()
            await session.commit()
    finally:
        if hasattr(provider, "_client") and hasattr(provider._client, "close"):
            await provider._client.close()
        await shutdown_engine()

    return {
        "since": result.since.isoformat(),
        "fetched": result.fetched,
        "created": result.created,
        "updated": result.updated,
        "unchanged": result.unchanged,
    }


@celery_app.task(name="ticket.poll_reconcile")
def poll_ticket_reconcile_task() -> dict[str, int | str]:
    """Beat task — query platform for updates and reconcile ticket_cache."""
    summary = asyncio.run(_poll_reconcile_async())
    logger.info("ticket_poll_reconcile_complete summary=%s", summary)
    return summary
