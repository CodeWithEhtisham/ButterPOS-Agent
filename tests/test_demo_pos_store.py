"""Tests for demo POS store (Task 1.7 / MCP demo)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo.pos_mcp.state import MenuItem, PosStore, PrinterState


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PosStore:
    path = tmp_path / "demo_store.json"
    monkeypatch.setattr("demo.pos_mcp.state.STORE_PATH", path)
    return PosStore()


def test_loads_existing_items(store: PosStore) -> None:
    store._seed_defaults()
    store._save()
    again = PosStore()
    assert len(again.list_items("demo-branch-karachi")) >= 3


def test_search_menu_items(store: PosStore) -> None:
    hits = store.search_items("demo-branch-karachi", "biryani")
    assert any("biryani" in i.name.lower() for i in hits)


def test_create_and_update_item(store: PosStore) -> None:
    item = store.create_item("demo-branch-karachi", "Test Dish", 99.0, "Main")
    updated = store.update_item(item.id, price=109.0)
    assert updated is not None
    assert updated.price == 109.0


def test_item_price_with_tax(store: PosStore) -> None:
    item = MenuItem("x", "demo-branch-karachi", "Tea", 100.0, "Beverage", 16.0)
    pricing = store.item_price_with_tax(item)
    assert pricing["price_with_tax"] == 116.0


def test_fix_printer(store: PosStore) -> None:
    printer = store.fix_printer("demo-branch-karachi", "restart")
    assert printer.status == "online"


def test_troubleshoot_printer_workflow(store: PosStore) -> None:
    with store._lock:
        if "demo-branch-karachi" not in store.printers:
            store.printers["demo-branch-karachi"] = PrinterState(branch_id="demo-branch-karachi")
        p = store.printers["demo-branch-karachi"]
        p.status = "offline"
        p.last_error = "Paper jam"
        p.pairing_strength = "disconnected"
        store._save()

    result = store.troubleshoot_printer("demo-branch-karachi")
    assert result["workflow"] == "printer_troubleshooting"
    assert len(result["steps"]) == 4
    assert result["steps"][0]["name"] == "check_printer"
    assert result["steps"][1]["name"] in {"check_printer_ip", "check_printer_pairing"}
    assert result["steps"][2]["name"] == "restart_printer"
    assert result["steps"][3]["name"] == "verify_printer_status"
    assert result["resolved"] is True


def test_persists_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "persist.json"
    monkeypatch.setattr("demo.pos_mcp.state.STORE_PATH", path)
    isolated = PosStore()
    isolated.create_item("demo-branch-karachi", "Persist Me", 50.0)
    raw = json.loads(path.read_text())
    assert any(i["name"] == "Persist Me" for i in raw["items"].values())
