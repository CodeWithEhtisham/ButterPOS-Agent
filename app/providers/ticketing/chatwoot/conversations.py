"""Chatwoot conversation API helpers — create, message, labels."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError
from app.providers.ticketing.chatwoot.mappers import unwrap_conversation

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


def parse_conversation_id(provider_ticket_id: str) -> int:
    try:
        return int(provider_ticket_id)
    except ValueError as exc:
        raise ChatwootAPIError(
            f"Invalid provider_ticket_id: {provider_ticket_id!r}",
            status_code=400,
        ) from exc


def parse_assignee_id(assignee_id: str) -> int:
    try:
        return int(assignee_id)
    except ValueError as exc:
        raise ChatwootAPIError(
            f"Invalid assignee_id: {assignee_id!r}",
            status_code=400,
        ) from exc


async def get_conversation(client: ChatwootClient, conversation_id: int) -> dict[str, Any]:
    """GET /conversations/{id}."""
    response = await client.request(
        "GET",
        client.account_path(f"/conversations/{conversation_id}"),
    )
    data = response.json()
    return data if isinstance(data, dict) else {}


async def toggle_conversation_status(
    client: ChatwootClient,
    conversation_id: int,
    *,
    status: str,
    snoozed_until: int | None = None,
) -> None:
    """POST /conversations/{id}/toggle_status."""
    payload: dict[str, Any] = {"status": status}
    if snoozed_until is not None:
        payload["snoozed_until"] = snoozed_until
    await client.request(
        "POST",
        client.account_path(f"/conversations/{conversation_id}/toggle_status"),
        json=payload,
    )
    logger.info(
        "Chatwoot conversation status toggled",
        extra={"conversation_id": conversation_id, "status": status},
    )


async def set_conversation_custom_attributes(
    client: ChatwootClient,
    conversation_id: int,
    custom_attributes: dict[str, Any],
) -> None:
    """POST /conversations/{id}/custom_attributes."""
    await client.request(
        "POST",
        client.account_path(f"/conversations/{conversation_id}/custom_attributes"),
        json={"custom_attributes": custom_attributes},
    )


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
    conversation_id = unwrap_conversation(data).get("id")
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
    content_type: str = "text",
    content_attributes: dict[str, Any] | None = None,
) -> None:
    """POST /conversations/{id}/messages — public reply or private agent note."""
    payload: dict[str, Any] = {
        "content": content,
        "message_type": "outgoing",
        "content_type": content_type,
        "private": private,
    }
    if content_attributes:
        payload["content_attributes"] = content_attributes

    await client.request(
        "POST",
        client.account_path(f"/conversations/{conversation_id}/messages"),
        json=payload,
    )
    logger.info(
        "Chatwoot message posted",
        extra={
            "conversation_id": conversation_id,
            "private": private,
            "content_type": content_type,
        },
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


async def assign_conversation_agent(
    client: ChatwootClient,
    conversation_id: int,
    assignee_id: int,
) -> None:
    """POST /conversations/{id}/assignments."""
    await client.request(
        "POST",
        client.account_path(f"/conversations/{conversation_id}/assignments"),
        json={"assignee_id": assignee_id},
    )
    logger.info(
        "Chatwoot conversation assigned",
        extra={"conversation_id": conversation_id, "assignee_id": assignee_id},
    )


async def append_conversation_labels(
    client: ChatwootClient,
    conversation_id: int,
    labels: list[str],
) -> list[str]:
    """Merge new labels with existing conversation labels and apply."""
    from app.providers.ticketing.chatwoot.mappers import conversation_to_standard_ticket

    raw = await get_conversation(client, conversation_id)
    existing = conversation_to_standard_ticket(raw).tags
    merged = list(dict.fromkeys([*existing, *labels]))
    await add_conversation_labels(client, conversation_id, merged)
    return merged


async def list_conversations_updated_since(
    client: ChatwootClient,
    since: datetime,
) -> list[dict[str, Any]]:
    """POST /conversations/filter — conversations updated after `since` in configured inbox."""
    since_epoch = int(since.timestamp())
    page = 1
    conversations: list[dict[str, Any]] = []

    while True:
        response = await client.request(
            "POST",
            client.account_path("/conversations/filter"),
            json={
                "payload": [
                    {
                        "attribute_key": "updated_at",
                        "filter_operator": "is_greater_than",
                        "values": [since_epoch],
                        "query_operator": "AND",
                    },
                    {
                        "attribute_key": "inbox_id",
                        "filter_operator": "equal_to",
                        "values": [client.inbox_id],
                        "query_operator": None,
                    },
                ],
                "page": page,
            },
        )
        body = response.json()
        if not isinstance(body, dict):
            break

        data = body.get("data") if isinstance(body.get("data"), dict) else body
        payload = data.get("payload") if isinstance(data, dict) else None
        if not isinstance(payload, list):
            payload = []

        for item in payload:
            if isinstance(item, dict):
                conversations.append(unwrap_conversation(item))

        meta = data.get("meta") if isinstance(data, dict) else {}
        if not isinstance(meta, dict):
            meta = {}
        total_pages = int(meta.get("total_pages") or page)
        if page >= total_pages or not payload:
            break
        page += 1

    return conversations
