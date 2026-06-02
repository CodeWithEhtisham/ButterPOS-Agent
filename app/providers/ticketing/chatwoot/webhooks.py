"""Chatwoot webhook verification, registration, and payload parsing."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from app.models.standard import MessageDirection, StandardEvent, StandardEventType
from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError, ChatwootConfigError
from app.providers.ticketing.chatwoot.mappers import parse_chatwoot_timestamp

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "x-chatwoot-signature"
TIMESTAMP_HEADER = "x-chatwoot-timestamp"
DEFAULT_MAX_AGE_SECONDS = 300

CHATWOOT_EVENT_MAP: dict[str, StandardEventType] = {
    "message_created": StandardEventType.MESSAGE_CREATED,
    "message_updated": StandardEventType.MESSAGE_UPDATED,
    "conversation_status_changed": StandardEventType.CONVERSATION_STATUS_CHANGED,
    "conversation_updated": StandardEventType.CONVERSATION_UPDATED,
    "webwidget_triggered": StandardEventType.WEBWIDGET_TRIGGERED,
}

DEFAULT_WEBHOOK_SUBSCRIPTIONS = [
    "message_created",
    "message_updated",
    "conversation_status_changed",
    "conversation_updated",
    "webwidget_triggered",
]


def _header(headers: dict[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def compute_chatwoot_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    """Compute expected X-Chatwoot-Signature value."""
    signed_payload = f"{timestamp}.".encode() + raw_body
    digest = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_chatwoot_webhook(
    raw_body: bytes,
    headers: dict[str, str],
    secret: str,
    *,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> bool:
    """Validate Chatwoot HMAC signature and timestamp window."""
    if not secret.strip():
        logger.warning("Chatwoot webhook verification skipped — secret not configured")
        return False

    received_signature = _header(headers, SIGNATURE_HEADER)
    timestamp_raw = _header(headers, TIMESTAMP_HEADER)
    if not received_signature or not timestamp_raw:
        return False

    try:
        timestamp = int(timestamp_raw)
    except ValueError:
        return False

    if abs(int(time.time()) - timestamp) > max_age_seconds:
        logger.warning("Chatwoot webhook rejected — timestamp outside allowed window")
        return False

    expected = compute_chatwoot_signature(secret, timestamp_raw, raw_body)
    return hmac.compare_digest(expected, received_signature)


def _extract_conversation_id(payload: dict[str, Any]) -> str | None:
    conversation = payload.get("conversation")
    if isinstance(conversation, dict) and conversation.get("id") is not None:
        return str(conversation["id"])
    event_name = str(payload.get("event", ""))
    if event_name.startswith("conversation") and payload.get("id") is not None:
        return str(payload["id"])
    return None


def _extract_provider_event_id(payload: dict[str, Any], event_name: str) -> str:
    if payload.get("id") is not None and event_name.startswith("message"):
        return str(payload["id"])
    conversation_id = _extract_conversation_id(payload)
    updated = payload.get("updated_at") or payload.get("created_at")
    if conversation_id and updated is not None:
        return f"{event_name}:{conversation_id}:{updated}"
    if conversation_id:
        return f"{event_name}:{conversation_id}"
    if payload.get("id") is not None:
        return str(payload["id"])
    return f"{event_name}:unknown"


def build_idempotency_key(payload: dict[str, Any], event_name: str) -> str:
    """Stable dedup key per WEBHOOKS.md conventions."""
    if event_name in {"message_created", "message_updated"} and payload.get("id") is not None:
        return f"{event_name}:{payload['id']}"
    conversation_id = _extract_conversation_id(payload)
    updated = payload.get("updated_at") or payload.get("created_at")
    if conversation_id and updated is not None:
        return f"{event_name}:{conversation_id}:{updated}"
    return _extract_provider_event_id(payload, event_name)


def _message_direction(payload: dict[str, Any]) -> MessageDirection | None:
    message_type = payload.get("message_type")
    if message_type == "incoming":
        return "incoming"
    if message_type == "outgoing":
        return "outgoing"
    return None


def _sender_contact_id(payload: dict[str, Any]) -> str | None:
    sender = payload.get("sender")
    if isinstance(sender, dict) and sender.get("type") == "contact" and sender.get("id") is not None:
        return str(sender["id"])
    return None


def _occurred_at(payload: dict[str, Any]) -> datetime:
    for key in ("created_at", "updated_at", "timestamp"):
        parsed = parse_chatwoot_timestamp(payload.get(key))
        if parsed is not None:
            return parsed
    return datetime.now(tz=UTC)


def parse_chatwoot_webhook(raw_body: bytes) -> StandardEvent:
    """Map raw Chatwoot webhook JSON to StandardEvent."""
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ChatwootAPIError("Invalid webhook JSON body", status_code=400) from exc

    if not isinstance(payload, dict):
        raise ChatwootAPIError("Webhook payload must be a JSON object", status_code=400)

    event_name = str(payload.get("event", "unknown"))
    event_type = CHATWOOT_EVENT_MAP.get(event_name, StandardEventType.UNKNOWN)
    provider_ticket_id = _extract_conversation_id(payload)
    if provider_ticket_id is None:
        raise ChatwootAPIError(
            f"Cannot resolve conversation id for event {event_name!r}",
            status_code=400,
        )

    message_body = payload.get("content")
    if message_body is not None and not isinstance(message_body, str):
        message_body = str(message_body)

    return StandardEvent(
        event_type=event_type,
        provider_event_id=_extract_provider_event_id(payload, event_name),
        provider_ticket_id=provider_ticket_id,
        occurred_at=_occurred_at(payload),
        message_body=message_body,
        message_direction=_message_direction(payload),
        sender_provider_contact_id=_sender_contact_id(payload),
        raw_payload=payload,
        idempotency_key=build_idempotency_key(payload, event_name),
    )


async def register_account_webhook(
    client: ChatwootClient,
    callback_url: str,
    *,
    subscriptions: list[str] | None = None,
    name: str = "ButterPOS Middleware",
) -> dict[str, Any]:
    """POST /webhooks — register account-level webhook (returns secret once)."""
    if not callback_url.strip():
        raise ChatwootConfigError("Webhook callback URL is required")

    payload = {
        "webhook": {
            "url": callback_url,
            "name": name,
            "subscriptions": subscriptions or DEFAULT_WEBHOOK_SUBSCRIPTIONS,
        },
    }
    response = await client.request(
        "POST",
        client.account_path("/webhooks"),
        json=payload,
    )
    data = response.json()
    logger.info(
        "Chatwoot account webhook registered",
        extra={"callback_url": callback_url, "subscriptions": payload["webhook"]["subscriptions"]},
    )
    return data if isinstance(data, dict) else {}
