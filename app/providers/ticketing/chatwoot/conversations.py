"""Chatwoot conversation API helpers — create, message, labels."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError

logger = logging.getLogger(__name__)


def build_source_id(contact_id: int, metadata: dict[str, Any]) -> str:
    """Stable-or-generated source_id required by API-channel inboxes."""
    existing = metadata.get("source_id")
    if existing:
        return str(existing)
    return f"butterpos-{contact_id}-{uuid.uuid4().hex[:12]}"


def parse_contact_id(provider_contact_id: str) -> int:
    try:
        return int(provider_contact_id)
    except ValueError as exc:
        raise ChatwootAPIError(
            f"Invalid provider_contact_id: {provider_contact_id!r}",
            status_code=400,
        ) from exc


async def create_conversation(
    client: ChatwootClient,
    *,
    contact_id: int,
    source_id: str,
    custom_attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """POST /conversations — open a new API-channel conversation."""
    payload: dict[str, Any] = {
        "source_id": source_id,
        "inbox_id": client.inbox_id,
        "contact_id": contact_id,
        "status": "open",
    }
    if custom_attributes:
        payload["custom_attributes"] = custom_attributes

    response = await client.request(
        "POST",
        client.account_path("/conversations"),
        json=payload,
    )
    data = response.json()
    conversation_id = _unwrap_conversation(data).get("id")
    logger.info(
        "Chatwoot conversation created",
        extra={
            "conversation_id": conversation_id,
            "contact_id": contact_id,
            "source_id": source_id,
        },
    )
    return data if isinstance(data, dict) else {}


async def send_conversation_message(
    client: ChatwootClient,
    conversation_id: int,
    *,
    content: str,
    private: bool = False,
) -> None:
    """POST /conversations/{id}/messages."""
    payload = {
        "content": content,
        "message_type": "outgoing",
        "content_type": "text",
        "private": private,
    }
    await client.request(
        "POST",
        client.account_path(f"/conversations/{conversation_id}/messages"),
        json=payload,
    )


async def add_conversation_labels(
    client: ChatwootClient,
    conversation_id: int,
    labels: list[str],
) -> None:
    """POST /conversations/{id}/labels."""
    if not labels:
        return
    await client.request(
        "POST",
        client.account_path(f"/conversations/{conversation_id}/labels"),
        json={"labels": labels},
    )


def _unwrap_conversation(data: dict[str, Any]) -> dict[str, Any]:
    if "conversation" in data and isinstance(data["conversation"], dict):
        return data["conversation"]
    if "payload" in data and isinstance(data["payload"], dict):
        payload = data["payload"]
        if "conversation" in payload and isinstance(payload["conversation"], dict):
            return payload["conversation"]
        return payload
    return data
