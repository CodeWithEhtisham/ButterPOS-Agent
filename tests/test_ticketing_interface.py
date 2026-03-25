"""Test TicketingProvider contract — verify all abstract methods exist."""

import inspect

from app.core.ticketing.interface import TicketingProvider


def test_ticketing_provider_has_all_abstract_methods():
    abstract_methods = {
        name for name, method in inspect.getmembers(TicketingProvider)
        if getattr(method, "__isabstractmethod__", False)
    }
    expected = {
        "create_ticket", "get_ticket", "update_status",
        "add_public_comment", "add_internal_note",
        "assign_agent", "add_tags",
        "get_or_create_contact",
        "verify_webhook", "parse_webhook",
        "health_check",
    }
    assert abstract_methods == expected, f"Missing: {expected - abstract_methods}, Extra: {abstract_methods - expected}"


def test_ticketing_provider_has_11_abstract_methods():
    abstract_methods = [
        name for name, method in inspect.getmembers(TicketingProvider)
        if getattr(method, "__isabstractmethod__", False)
    ]
    assert len(abstract_methods) == 11
