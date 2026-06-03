"""Ticket cache persistence — durable mirror for polling reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.db.models.ticket_cache import TicketCache
from app.models.standard import StandardTicket
from app.providers.ticketing.base import TicketingProvider

logger = get_logger("app.ticket_cache")

TicketCacheSyncAction = Literal["created", "updated", "unchanged"]


async def get_ticket_cache_by_provider_id(
    session: AsyncSession,
    provider_ticket_id: str,
) -> TicketCache | None:
    """Load a cached ticket row by platform conversation id."""
    return await session.scalar(
        select(TicketCache).where(TicketCache.provider_ticket_id == provider_ticket_id),
    )


async def get_or_fetch_ticket_cache(
    session: AsyncSession,
    ticketing: TicketingProvider,
    provider_ticket_id: str,
) -> TicketCache:
    """Return ticket_cache row, fetching from the ticketing platform when missing."""
    row = await get_ticket_cache_by_provider_id(session, provider_ticket_id)
    if row is not None:
        return row

    ticket = await ticketing.get_ticket(provider_ticket_id)
    await upsert_ticket_cache(session, ticket)
    row = await get_ticket_cache_by_provider_id(session, provider_ticket_id)
    if row is None:
        raise RuntimeError(f"ticket_cache insert failed for {provider_ticket_id}")
    return row


@dataclass(frozen=True)
class TicketCacheSyncResult:
    """Outcome of upserting one platform ticket into Postgres mirror."""

    provider_ticket_id: str
    action: TicketCacheSyncAction


def _ticket_changed(row: TicketCache, ticket: StandardTicket) -> bool:
    return (
        row.status != ticket.status.value
        or row.subject != ticket.subject
        or row.provider_contact_id != ticket.provider_contact_id
        or row.assignee_id != ticket.assignee_id
        or row.tags != ticket.tags
        or row.meta != ticket.metadata
    )


async def upsert_ticket_cache(
    session: AsyncSession,
    ticket: StandardTicket,
) -> TicketCacheSyncResult:
    """Insert or update ticket_cache from a StandardTicket platform snapshot."""
    now = datetime.now(tz=UTC)
    row = await session.scalar(
        select(TicketCache).where(TicketCache.provider_ticket_id == ticket.provider_ticket_id)
    )

    if row is None:
        session.add(
            TicketCache(
                provider_ticket_id=ticket.provider_ticket_id,
                status=ticket.status.value,
                subject=ticket.subject,
                provider_contact_id=ticket.provider_contact_id,
                assignee_id=ticket.assignee_id,
                tags=ticket.tags,
                meta=ticket.metadata,
                synced_at=now,
            )
        )
        await session.flush()
        logger.info(
            "ticket_cache_created provider_ticket_id=%s",
            ticket.provider_ticket_id,
            extra={"ticket_id": ticket.provider_ticket_id},
        )
        return TicketCacheSyncResult(ticket.provider_ticket_id, "created")

    if _ticket_changed(row, ticket):
        row.status = ticket.status.value
        row.subject = ticket.subject
        row.provider_contact_id = ticket.provider_contact_id
        row.assignee_id = ticket.assignee_id
        row.tags = ticket.tags
        row.meta = ticket.metadata
        row.synced_at = now
        await session.flush()
        logger.info(
            "ticket_cache_updated provider_ticket_id=%s",
            ticket.provider_ticket_id,
            extra={"ticket_id": ticket.provider_ticket_id},
        )
        return TicketCacheSyncResult(ticket.provider_ticket_id, "updated")

    row.synced_at = now
    await session.flush()
    return TicketCacheSyncResult(ticket.provider_ticket_id, "unchanged")
