"""Guided printer troubleshooting workflow for demo MCP."""

from __future__ import annotations

from typing import Any

from demo.pos_mcp.state import PosStore, PrinterState


def _printer_snapshot(printer: PrinterState) -> dict[str, object]:
    return {
        "printer_name": printer.printer_name,
        "status": printer.status,
        "connection": printer.connection,
        "ip_address": printer.ip_address,
        "network_reachable": printer.network_reachable,
        "last_print_at": printer.last_print_at,
        "last_error": printer.last_error,
        "queue_depth": printer.queue_depth,
        "pairing_strength": printer.pairing_strength,
    }


def _check_network_locked(store: PosStore, printer: PrinterState) -> dict[str, object]:
    """Step 2 — verify network path (IP ping) or Bluetooth pairing."""
    conn = printer.connection.lower()
    if conn in {"network", "wifi", "ethernet", "lan"}:
        if not printer.ip_address:
            printer.ip_address = "192.168.1.88"
        reachable = printer.status == "online" and printer.network_reachable is not False
        printer.network_reachable = reachable
        return {
            "step": 2,
            "name": "check_printer_ip",
            "status": "ok" if reachable else "failed",
            "connection": printer.connection,
            "ip_address": printer.ip_address,
            "ping_ok": reachable,
            "detail": (
                f"Printer at {printer.ip_address} is reachable on the LAN."
                if reachable
                else f"Cannot reach printer at {printer.ip_address} — check cable/Wi‑Fi."
            ),
        }

    printer.ip_address = None
    pairing = printer.pairing_strength or (
        "strong" if printer.status == "online" else "disconnected"
    )
    printer.pairing_strength = pairing
    pairing_ok = pairing in {"strong", "good"}
    return {
        "step": 2,
        "name": "check_printer_pairing",
        "status": "ok" if pairing_ok else "failed",
        "connection": printer.connection,
        "ip_address": None,
        "pairing_strength": pairing,
        "detail": (
            "Bluetooth pairing is healthy."
            if pairing_ok
            else "Bluetooth pairing is weak or lost — restart usually fixes this."
        ),
    }


def run_printer_troubleshooting(store: PosStore, branch_id: str) -> dict[str, Any]:
    """
    Agent-style printer fix runbook (executed in order):

    1. check_printer — initial status
    2. check_printer_ip / pairing — network path
    3. restart_printer — apply fix
    4. check_printer — verify final status
    """
    steps: list[dict[str, object]] = []

    with store._lock:
        if branch_id not in store.printers:
            store.printers[branch_id] = PrinterState(branch_id=branch_id)
        printer = store.printers[branch_id]

        # Step 1 — initial diagnostics
        step1_status = "ok" if printer.status == "online" and not printer.last_error else "failed"
        steps.append(
            {
                "step": 1,
                "name": "check_printer",
                "status": step1_status,
                "detail": (
                    f"Printer '{printer.printer_name}' is {printer.status} "
                    f"via {printer.connection}."
                    + (f" Last error: {printer.last_error}" if printer.last_error else "")
                ),
                "printer": _printer_snapshot(printer),
            }
        )

        already_healthy = (
            printer.status == "online"
            and not printer.last_error
            and printer.queue_depth == 0
        )

        # Step 2 — IP / pairing (always run for a complete diagnostic trail)
        steps.append(_check_network_locked(store, printer))
        network_ok = steps[-1]["status"] == "ok"

        needs_fix = not already_healthy or not network_ok or printer.queue_depth > 0

        # Step 3 — restart (skip only when fully healthy)
        if needs_fix:
            before = printer.status
            action = "restart" if printer.connection.lower() == "bluetooth" else "reconnect"
            if printer.connection.lower() in {"network", "wifi", "ethernet", "lan"}:
                action = "restart"
            store._apply_printer_fix_locked(printer, action)
            steps.append(
                {
                    "step": 3,
                    "name": "restart_printer",
                    "status": "ok" if printer.status == "online" else "failed",
                    "action": action,
                    "detail": (
                        f"Executed '{action}' on {printer.printer_name}."
                    ),
                    "previous_status": before,
                    "printer": _printer_snapshot(printer),
                }
            )
        else:
            steps.append(
                {
                    "step": 3,
                    "name": "restart_printer",
                    "status": "skipped",
                    "detail": "Printer already healthy — restart not required.",
                }
            )

        # Step 4 — verify
        resolved = printer.status == "online" and not printer.last_error
        steps.append(
            {
                "step": 4,
                "name": "verify_printer_status",
                "status": "ok" if resolved else "failed",
                "detail": (
                    "Printer is online and ready to print."
                    if resolved
                    else (
                        f"Printer still {printer.status}. "
                        f"{printer.last_error or 'Escalate to on-site support.'}"
                    )
                ),
                "printer": _printer_snapshot(printer),
            }
        )

        store._save()

    summary = (
        "Printer issue resolved — receipt printer is online."
        if resolved
        else "Printer still not ready after automated troubleshooting — escalate to a human agent."
    )
    return {
        "workflow": "printer_troubleshooting",
        "branch_id": branch_id,
        "resolved": resolved,
        "steps": steps,
        "summary": summary,
        "recommendation": (
            "Ask staff to print a test receipt."
            if resolved
            else "Check power/USB cable, then contact ButterPOS support with this log."
        ),
    }
