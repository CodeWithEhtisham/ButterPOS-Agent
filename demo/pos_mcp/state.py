"""In-memory Restaurant POS state for demo MCP tools — persisted to JSON."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

STORE_PATH = Path(__file__).resolve().parent / "demo_store.json"


@dataclass
class MenuItem:
    id: str
    branch_id: str
    name: str
    price: float
    category: str
    tax_rate_percent: float | None = None


@dataclass
class PrinterState:
    branch_id: str
    printer_name: str = "EPSON-TM-T88VI"
    status: str = "offline"
    connection: str = "bluetooth"
    ip_address: str | None = None
    network_reachable: bool | None = None
    pairing_strength: str | None = None
    last_print_at: str | None = None
    last_error: str | None = "Bluetooth pairing lost"
    queue_depth: int = 0


@dataclass
class PosStore:
    """Thread-safe demo POS — loads/saves JSON so MCP processes share state."""

    branch_id: str = "demo-branch-karachi"
    currency: str = "PKR"
    default_tax_rate_percent: float = 16.0
    items: dict[str, MenuItem] = field(default_factory=dict)
    branch_tax_rates: dict[str, float] = field(default_factory=dict)
    printers: dict[str, PrinterState] = field(default_factory=dict)
    order_count_today: int = 47
    gross_total_today: float = 125_400.0
    _lock: Lock = field(default_factory=Lock, repr=False)
    _path: Path = field(default_factory=lambda: STORE_PATH, repr=False)

    def __post_init__(self) -> None:
        if self._path.exists():
            self._load()
        else:
            self._seed_defaults()
            self._save()

    def _seed_defaults(self) -> None:
        if not self.items:
            for item in (
                MenuItem("item-1", self.branch_id, "Chicken Biryani", 450.0, "Main", 16.0),
                MenuItem("item-2", self.branch_id, "Karahi", 1200.0, "Main", 16.0),
                MenuItem("item-3", self.branch_id, "Cold Drink", 150.0, "Beverage", 16.0),
            ):
                self.items[item.id] = item
        if self.branch_id not in self.branch_tax_rates:
            self.branch_tax_rates[self.branch_id] = self.default_tax_rate_percent
        if self.branch_id not in self.printers:
            self.printers[self.branch_id] = PrinterState(branch_id=self.branch_id)

    def _load(self) -> None:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self.branch_id = raw.get("branch_id", self.branch_id)
        self.currency = raw.get("currency", self.currency)
        self.default_tax_rate_percent = float(raw.get("default_tax_rate_percent", 16.0))
        self.order_count_today = int(raw.get("order_count_today", 47))
        self.gross_total_today = float(raw.get("gross_total_today", 125_400.0))
        self.branch_tax_rates = {k: float(v) for k, v in raw.get("branch_tax_rates", {}).items()}
        self.items = {k: MenuItem(**v) for k, v in raw.get("items", {}).items()}
        self.printers = {}
        for k, v in raw.get("printers", {}).items():
            known = {f.name for f in PrinterState.__dataclass_fields__.values()}
            self.printers[k] = PrinterState(**{key: val for key, val in v.items() if key in known})
        if not self.items:
            self._seed_defaults()

    def _save(self) -> None:
        payload = {
            "branch_id": self.branch_id,
            "currency": self.currency,
            "default_tax_rate_percent": self.default_tax_rate_percent,
            "order_count_today": self.order_count_today,
            "gross_total_today": self.gross_total_today,
            "branch_tax_rates": self.branch_tax_rates,
            "items": {k: asdict(v) for k, v in self.items.items()},
            "printers": {k: asdict(v) for k, v in self.printers.items()},
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _now_iso(self) -> str:
        return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def list_items(self, branch_id: str) -> list[MenuItem]:
        with self._lock:
            return [item for item in self.items.values() if item.branch_id == branch_id]

    def get_item(self, item_id: str) -> MenuItem | None:
        with self._lock:
            return self.items.get(item_id)

    def search_items(self, branch_id: str, query: str) -> list[MenuItem]:
        q = query.strip().lower()
        return [
            item
            for item in self.list_items(branch_id)
            if q in item.name.lower() or q in item.category.lower()
        ]

    def create_item(
        self,
        branch_id: str,
        name: str,
        price: float,
        category: str = "Main",
    ) -> MenuItem:
        with self._lock:
            item_id = f"item-{uuid.uuid4().hex[:8]}"
            tax = self.branch_tax_rates.get(branch_id, self.default_tax_rate_percent)
            item = MenuItem(
                id=item_id,
                branch_id=branch_id,
                name=name.strip(),
                price=float(price),
                category=category.strip() or "Main",
                tax_rate_percent=tax,
            )
            self.items[item_id] = item
            self._save()
            return item

    def update_item(
        self,
        item_id: str,
        *,
        name: str | None = None,
        price: float | None = None,
        category: str | None = None,
    ) -> MenuItem | None:
        with self._lock:
            item = self.items.get(item_id)
            if item is None:
                return None
            if name is not None and name.strip():
                item.name = name.strip()
            if price is not None:
                item.price = float(price)
            if category is not None and category.strip():
                item.category = category.strip()
            self._save()
            return item

    def set_item_tax(self, item_id: str, tax_rate_percent: float) -> MenuItem | None:
        with self._lock:
            item = self.items.get(item_id)
            if item is None:
                return None
            item.tax_rate_percent = float(tax_rate_percent)
            self._save()
            return item

    def get_branch_tax(self, branch_id: str) -> float:
        with self._lock:
            return self.branch_tax_rates.get(branch_id, self.default_tax_rate_percent)

    def set_branch_tax(self, branch_id: str, tax_rate_percent: float) -> float:
        with self._lock:
            rate = float(tax_rate_percent)
            self.branch_tax_rates[branch_id] = rate
            self._save()
            return rate

    def item_price_with_tax(self, item: MenuItem) -> dict[str, float | str]:
        tax_rate = (
            item.tax_rate_percent
            if item.tax_rate_percent is not None
            else self.get_branch_tax(item.branch_id)
        )
        tax_amount = round(item.price * tax_rate / 100, 2)
        return {
            "item_id": item.id,
            "name": item.name,
            "base_price": item.price,
            "tax_rate_percent": tax_rate,
            "tax_amount": tax_amount,
            "price_with_tax": round(item.price + tax_amount, 2),
            "currency": self.currency,
        }

    def check_printer(self, branch_id: str) -> PrinterState:
        with self._lock:
            if branch_id not in self.printers:
                self.printers[branch_id] = PrinterState(branch_id=branch_id)
            return self.printers[branch_id]

    def _apply_printer_fix_locked(self, printer: PrinterState, action: str) -> None:
        action_norm = action.strip().lower()
        if action_norm in {"restart", "reconnect", "clear_queue"}:
            if action_norm == "clear_queue":
                printer.queue_depth = 0
            printer.status = "online"
            printer.last_error = None
            printer.last_print_at = self._now_iso()
            printer.network_reachable = True
            printer.pairing_strength = "strong"
        else:
            printer.last_error = f"Unknown action: {action}"

    def fix_printer(self, branch_id: str, action: str) -> PrinterState:
        with self._lock:
            if branch_id not in self.printers:
                self.printers[branch_id] = PrinterState(branch_id=branch_id)
            printer = self.printers[branch_id]
            self._apply_printer_fix_locked(printer, action)
            self._save()
            return printer

    def get_printer_network(self, branch_id: str) -> dict[str, object]:
        """Network / pairing check for step 2 of printer runbook."""
        with self._lock:
            if branch_id not in self.printers:
                self.printers[branch_id] = PrinterState(branch_id=branch_id)
            printer = self.printers[branch_id]
            from demo.pos_mcp.printer_workflow import _check_network_locked

            result = _check_network_locked(self, printer)
            self._save()
            return result

    def troubleshoot_printer(self, branch_id: str) -> dict[str, object]:
        """Run full printer agent workflow (check → IP/pairing → restart → verify)."""
        from demo.pos_mcp.printer_workflow import run_printer_troubleshooting

        return run_printer_troubleshooting(self, branch_id)


def get_store() -> PosStore:
    return PosStore()


STORE = get_store()
