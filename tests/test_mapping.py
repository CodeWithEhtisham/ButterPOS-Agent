"""Test customer/branch mapping and standard models."""

from app.core.ticketing.models import StandardStatus, StandardPriority, StandardEventType


def test_standard_status_has_12_values():
    assert len(StandardStatus) == 12


def test_standard_priority_values():
    assert set(StandardPriority) == {
        StandardPriority.LOW,
        StandardPriority.MEDIUM,
        StandardPriority.HIGH,
        StandardPriority.CRITICAL,
    }


def test_standard_event_type_values():
    expected = {
        "ticket_created", "ticket_updated", "status_changed",
        "comment_added", "internal_note_added", "agent_assigned",
        "ticket_closed", "ticket_reopened",
    }
    actual = {e.value for e in StandardEventType}
    assert actual == expected
