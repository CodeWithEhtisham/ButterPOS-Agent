"""Tests for Standard* Pydantic models — Task 1.1.5."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.models.standard import (
    CreateTicketRequest,
    StandardEvent,
    StandardEventType,
    StandardStatus,
    StandardTicket,
)
from pydantic import ValidationError


def test_standard_status_has_twelve_values() -> None:
    assert len(StandardStatus) == 12


def test_standard_ticket_roundtrip() -> None:
    ticket = StandardTicket(
        provider_ticket_id="conv-5678",
        status=StandardStatus.OPEN,
        subject="Printer issue",
        provider_contact_id="contact-101",
        tags=["printer", "tier1"],
    )
    data = ticket.model_dump()
    restored = StandardTicket.model_validate(data)
    assert restored == ticket


def test_standard_event_from_message_created() -> None:
    event = StandardEvent(
        event_type=StandardEventType.MESSAGE_CREATED,
        provider_event_id="msg-12345",
        provider_ticket_id="conv-5678",
        occurred_at=datetime.now(UTC),
        message_body="Printer offline hai",
        message_direction="incoming",
        sender_provider_contact_id="contact-101",
        idempotency_key="message_created:12345",
    )
    assert event.event_type == StandardEventType.MESSAGE_CREATED


def test_create_ticket_request_requires_contact() -> None:
    with pytest.raises(ValidationError):
        CreateTicketRequest.model_validate({})
