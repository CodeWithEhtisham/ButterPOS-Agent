"""In-memory session fake for ticket_cache repository tests."""

from __future__ import annotations

from typing import Any

from app.db.models.ticket_cache import TicketCache


def _provider_ticket_id_from_statement(statement: Any) -> str | None:
    whereclause = getattr(statement, "whereclause", None)
    if whereclause is None:
        return None
    right = getattr(whereclause, "right", None)
    value = getattr(right, "value", None)
    if value is not None:
        return str(value)
    return None


class TicketCacheMemorySession:
    """Minimal async session double for ticket_cache upsert tests."""

    def __init__(self) -> None:
        self._rows: dict[str, TicketCache] = {}
        self._pending: TicketCache | None = None

    def add(self, obj: TicketCache) -> None:
        self._pending = obj

    async def flush(self) -> None:
        if self._pending is not None:
            self._rows[self._pending.provider_ticket_id] = self._pending
            self._pending = None

    async def scalar(self, statement: Any) -> TicketCache | None:
        ticket_id = _provider_ticket_id_from_statement(statement)
        if ticket_id is None:
            return None
        return self._rows.get(ticket_id)

    def row(self, provider_ticket_id: str) -> TicketCache:
        return self._rows[provider_ticket_id]
