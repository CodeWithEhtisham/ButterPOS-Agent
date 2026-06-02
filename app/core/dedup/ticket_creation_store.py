"""Ticket creation dedup store factory — no TicketingProvider imports."""

from __future__ import annotations

from app.core.config import Settings
from app.core.dedup.store import DedupStore, RedisDedupStore

DEDUP_METADATA_KEYS = ("client_request_id", "source_id", "idempotency_key")


def extract_ticket_creation_dedup_key(
    metadata: dict[str, object],
    *,
    key_names: tuple[str, ...] | None = None,
) -> str | None:
    """Client-supplied id — required for dedup; omitted keys always create a new ticket."""
    names = key_names or DEDUP_METADATA_KEYS
    for name in names:
        value = metadata.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def build_ticket_creation_dedup_store(settings: Settings) -> DedupStore:
    return RedisDedupStore(
        settings.redis_url,
        key_prefix=settings.request_dedup_redis_prefix,
        lock_ttl_seconds=settings.request_dedup_lock_ttl_seconds,
    )
