"""Map Chatwoot API payloads to platform-agnostic standard models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.standard import StandardStatus, StandardTicket

CHATWOOT_TO_STANDARD_STATUS: dict[str, StandardStatus] = {
    "open": StandardStatus.OPEN,
    "resolved": StandardStatus.RESOLVED,
    "pending": StandardStatus.PENDING,
    "snoozed": StandardStatus.SNOOZED,
}


def chatwoot_status_to_standard(status: str) -> StandardStatus:
    """Map Chatwoot conversation status to StandardStatus (expanded in Task 1.3.3)."""
    return CHATWOOT_TO_STANDARD_STATUS.get(status.lower(), StandardStatus.OPEN)


def parse_chatwoot_timestamp(value: Any) -> datetime | None:
    """Parse Chatwoot epoch seconds or ISO-8601 timestamps."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    return None


def _unwrap_conversation(data: dict[str, Any]) -> dict[str, Any]:
    if "conversation" in data and isinstance(data["conversation"], dict):
        return data["conversation"]
    if "payload" in data and isinstance(data["payload"], dict):
        payload = data["payload"]
        if "conversation" in payload and isinstance(payload["conversation"], dict):
            return payload["conversation"]
        return payload
    return data


def _extract_contact_id(conversation: dict[str, Any]) -> str | None:
    contact = conversation.get("contact")
    if isinstance(contact, dict) and contact.get("id") is not None:
        return str(contact["id"])
    if conversation.get("contact_id") is not None:
        return str(conversation["contact_id"])
    return None


def _extract_assignee_id(conversation: dict[str, Any]) -> str | None:
    assignee = conversation.get("assignee")
    if isinstance(assignee, dict) and assignee.get("id") is not None:
        return str(assignee["id"])
    if conversation.get("assignee_id") is not None:
        return str(conversation["assignee_id"])
    return None


def _extract_tags(conversation: dict[str, Any]) -> list[str]:
    labels = conversation.get("labels") or []
    tags: list[str] = []
    for label in labels:
        if isinstance(label, str):
            tags.append(label)
        elif isinstance(label, dict):
            title = label.get("title") or label.get("name")
            if title:
                tags.append(str(title))
    return tags


def conversation_to_standard_ticket(
    data: dict[str, Any],
    *,
    subject: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> StandardTicket:
    """Convert Chatwoot conversation JSON to StandardTicket."""
    conversation = _unwrap_conversation(data)
    conv_id = conversation.get("id")
    if conv_id is None:
        raise ValueError("Chatwoot conversation response missing id")

    metadata = dict(extra_metadata or {})
    custom_attributes = conversation.get("custom_attributes")
    if isinstance(custom_attributes, dict):
        metadata.update(custom_attributes)

    return StandardTicket(
        provider_ticket_id=str(conv_id),
        status=chatwoot_status_to_standard(str(conversation.get("status", "open"))),
        subject=subject,
        provider_contact_id=_extract_contact_id(conversation),
        assignee_id=_extract_assignee_id(conversation),
        tags=_extract_tags(conversation),
        created_at=parse_chatwoot_timestamp(conversation.get("created_at")),
        updated_at=parse_chatwoot_timestamp(
            conversation.get("last_activity_at") or conversation.get("updated_at")
        ),
        metadata=metadata,
    )
