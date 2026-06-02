"""In-memory AsyncSession fake for webhook idempotency tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.db.models.webhook_event_log import WebhookEventLog


class IdempotencyMemorySession:
    """Minimal session double — supports add/flush/rollback/scalar for webhook dedupe."""

    def __init__(self) -> None:
        self._rows: dict[str, WebhookEventLog] = {}
        self._pending: WebhookEventLog | None = None
        self._last_conflict_key: str | None = None

    def add(self, obj: WebhookEventLog) -> None:
        self._pending = obj

    async def flush(self) -> None:
        if self._pending is None:
            return
        key = self._pending.idempotency_key
        if key in self._rows:
            self._last_conflict_key = key
            self._pending = None
            raise IntegrityError("", {}, Exception())
        self._rows[key] = self._pending
        self._pending = None

    async def rollback(self) -> None:
        self._pending = None

    async def commit(self) -> None:
        return None

    async def scalar(self, statement: Any) -> WebhookEventLog | None:
        if self._last_conflict_key is not None:
            key = self._last_conflict_key
            self._last_conflict_key = None
            return self._rows.get(key)

        key = _idempotency_key_from_statement(statement)
        if key is not None:
            return self._rows.get(key)

        if len(self._rows) == 1:
            return next(iter(self._rows.values()))
        return None


def _idempotency_key_from_statement(statement: Any) -> str | None:
    """Best-effort extract idempotency_key from SQLAlchemy select used in tests."""
    try:
        where = statement._where_criteria
    except AttributeError:
        return None
    for criterion in where:
        left = getattr(criterion, "left", None)
        right = getattr(criterion, "right", None)
        if getattr(left, "key", None) == "idempotency_key" and right is not None:
            value = getattr(right, "value", right)
            return str(value)
    return None


async def memory_webhook_session() -> AsyncGenerator[IdempotencyMemorySession, None]:
    """FastAPI dependency override — in-memory idempotency store."""
    session = IdempotencyMemorySession()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    else:
        await session.commit()
