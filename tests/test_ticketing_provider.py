"""Tests for TicketingProvider interface — Task 1.1.4."""

from __future__ import annotations

import inspect

from app.providers.ticketing.base import TicketingProvider

REQUIRED_METHODS = frozenset(
    {
        "create_ticket",
        "get_ticket",
        "update_status",
        "add_comment",
        "add_note",
        "assign_agent",
        "add_tags",
        "get_or_create_contact",
        "verify_webhook",
        "parse_webhook",
        "health_check",
    }
)


def test_ticketing_provider_is_abstract() -> None:
    assert TicketingProvider.__abstractmethods__ == REQUIRED_METHODS


def test_cannot_instantiate_ticketing_provider() -> None:
    try:
        TicketingProvider()  # type: ignore[abstract]
        raised = False
    except TypeError:
        raised = True
    assert raised


def test_all_methods_are_async() -> None:
    for name in REQUIRED_METHODS:
        method = getattr(TicketingProvider, name)
        assert inspect.iscoroutinefunction(method), f"{name} must be async"
