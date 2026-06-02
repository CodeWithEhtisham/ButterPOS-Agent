"""Plan expiry evaluation — pure logic for Task 1.6."""

from __future__ import annotations

from datetime import UTC, datetime


def is_plan_expired(expiry: datetime | None, *, now: datetime) -> bool:
    """Return True when plan expiry is set and in the past."""
    if expiry is None:
        return False
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return expiry < now
