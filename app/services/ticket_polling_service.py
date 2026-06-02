"""Ticket polling reconciliation — platform ↔ Postgres ticket_cache mirror."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging_config import get_logger
from app.providers.ticketing.base import TicketingProvider
from app.repositories.ticket_cache_repository import TicketCacheSyncResult, upsert_ticket_cache
from app.worker.polling_state import InMemoryPollingCursorStore, PollingCursorStore

logger = get_logger("app.polling")


@dataclass(frozen=True)
class PollingReconcileResult:
    """Summary of one polling sweep."""

    since: datetime
    fetched: int
    created: int
    updated: int
    unchanged: int


class TicketPollingService:
    """Query ticketing platform and reconcile ticket_cache rows."""

    def __init__(
        self,
        provider: TicketingProvider,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        cursor_store: PollingCursorStore | InMemoryPollingCursorStore | None = None,
    ) -> None:
        self._provider = provider
        self._session = session
        self._settings = settings or get_settings()
        self._cursor_store = cursor_store

    def _get_cursor_store(self) -> PollingCursorStore | InMemoryPollingCursorStore:
        if self._cursor_store is not None:
            return self._cursor_store
        from app.worker.polling_state import get_polling_cursor_store

        return get_polling_cursor_store()

    def _resolve_since(self, cursor: PollingCursorStore | InMemoryPollingCursorStore) -> datetime:
        last_sync = cursor.get_last_sync()
        if last_sync is not None:
            return last_sync
        lookback = timedelta(seconds=self._settings.webhook_polling_initial_lookback_seconds)
        return datetime.now(tz=UTC) - lookback

    async def reconcile(self) -> PollingReconcileResult:
        """Fetch platform updates since last cursor and upsert ticket_cache."""
        cursor = self._get_cursor_store()
        since = self._resolve_since(cursor)
        tickets = await self._provider.list_tickets_updated_since(since)

        created = updated = unchanged = 0
        results: list[TicketCacheSyncResult] = []
        for ticket in tickets:
            results.append(await upsert_ticket_cache(self._session, ticket))

        for result in results:
            if result.action == "created":
                created += 1
            elif result.action == "updated":
                updated += 1
            else:
                unchanged += 1

        finished_at = datetime.now(tz=UTC)
        cursor.set_last_sync(finished_at)

        logger.info(
            "ticket_poll_reconcile since=%s fetched=%s created=%s updated=%s unchanged=%s",
            since.isoformat(),
            len(tickets),
            created,
            updated,
            unchanged,
            extra={
                "fetched": len(tickets),
                "created": created,
                "updated": updated,
                "unchanged": unchanged,
            },
        )
        return PollingReconcileResult(
            since=since,
            fetched=len(tickets),
            created=created,
            updated=updated,
            unchanged=unchanged,
        )
