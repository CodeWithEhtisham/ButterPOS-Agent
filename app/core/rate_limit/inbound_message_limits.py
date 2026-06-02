"""Inbound customer message rate limits — Task 1.5.2."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import RateLimitExceededError
from app.core.logging_config import get_logger
from app.core.rate_limit.sliding_window import (
    InMemorySlidingWindowRateLimiter,
    RedisSlidingWindowRateLimiter,
    SlidingWindowRateLimiter,
)
from app.models.standard import StandardEvent, StandardEventType

logger = get_logger("app.rate_limit")

RESTAURANT_ID_ATTRS = ("restaurant_id", "butterpos_restaurant_id")


def should_rate_limit_inbound_message(event: StandardEvent) -> bool:
    """Only count new incoming customer messages."""
    if event.event_type is not StandardEventType.MESSAGE_CREATED:
        return False
    return event.message_direction == "incoming"


def extract_user_rate_limit_key(event: StandardEvent) -> str | None:
    """User scope — Chatwoot contact id until Task 1.6 maps ButterPOS user ids."""
    if event.sender_provider_contact_id:
        return event.sender_provider_contact_id
    sender = event.raw_payload.get("sender")
    if isinstance(sender, dict) and sender.get("id") is not None:
        return str(sender["id"])
    return None


def extract_restaurant_rate_limit_key(event: StandardEvent) -> str | None:
    """Restaurant scope — from conversation custom_attributes when present."""
    conversation = event.raw_payload.get("conversation")
    if isinstance(conversation, dict):
        found = _restaurant_id_from_attrs(conversation.get("custom_attributes"))
        if found:
            return found
    meta = event.raw_payload.get("meta")
    if isinstance(meta, dict):
        found = _restaurant_id_from_attrs(meta.get("custom_attributes"))
        if found:
            return found
    return _restaurant_id_from_attrs(event.raw_payload.get("custom_attributes"))


def _restaurant_id_from_attrs(attrs: Any) -> str | None:
    if not isinstance(attrs, dict):
        return None
    for name in RESTAURANT_ID_ATTRS:
        value = attrs.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


class InboundMessageRateLimiter:
    """Enforce per-user and per-restaurant message quotas."""

    def __init__(
        self,
        user_limiter: SlidingWindowRateLimiter,
        restaurant_limiter: SlidingWindowRateLimiter,
    ) -> None:
        self._user_limiter = user_limiter
        self._restaurant_limiter = restaurant_limiter

    async def check(self, event: StandardEvent) -> None:
        """Raise RateLimitExceededError when an inbound message exceeds quotas."""
        if not should_rate_limit_inbound_message(event):
            return

        user_key = extract_user_rate_limit_key(event)
        if user_key is not None:
            allowed = await self._user_limiter.allow(user_key)
            if not allowed:
                logger.warning(
                    "rate_limit_user_exceeded user_key=%s ticket_id=%s",
                    user_key,
                    event.provider_ticket_id,
                    extra={"user_id": user_key, "ticket_id": event.provider_ticket_id},
                )
                raise RateLimitExceededError("User message rate limit exceeded")

        restaurant_key = extract_restaurant_rate_limit_key(event)
        if restaurant_key is not None:
            allowed = await self._restaurant_limiter.allow(restaurant_key)
            if not allowed:
                logger.warning(
                    "rate_limit_restaurant_exceeded restaurant_key=%s ticket_id=%s",
                    restaurant_key,
                    event.provider_ticket_id,
                    extra={"restaurant_id": restaurant_key, "ticket_id": event.provider_ticket_id},
                )
                raise RateLimitExceededError("Restaurant message rate limit exceeded")


def build_inbound_message_rate_limiter(
    settings: Settings,
    *,
    user_limiter: SlidingWindowRateLimiter | None = None,
    restaurant_limiter: SlidingWindowRateLimiter | None = None,
) -> InboundMessageRateLimiter:
    user = user_limiter or RedisSlidingWindowRateLimiter(
        settings.redis_url,
        key_prefix=settings.rate_limit_user_redis_prefix,
        limit=settings.rate_limit_user_messages_per_hour,
        window_seconds=settings.rate_limit_user_window_seconds,
    )
    restaurant = restaurant_limiter or RedisSlidingWindowRateLimiter(
        settings.redis_url,
        key_prefix=settings.rate_limit_restaurant_redis_prefix,
        limit=settings.rate_limit_restaurant_messages_per_day,
        window_seconds=settings.rate_limit_restaurant_window_seconds,
    )
    return InboundMessageRateLimiter(user, restaurant)


@lru_cache
def get_inbound_message_rate_limiter() -> InboundMessageRateLimiter:
    return build_inbound_message_rate_limiter(get_settings())


def clear_inbound_message_rate_limiter_cache() -> None:
    get_inbound_message_rate_limiter.cache_clear()
