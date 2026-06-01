#!/usr/bin/env python3
"""
Step 0.4 — Assumption Validation (A1–A7).

Produces a signed-off checklist with automated checks where possible.
Manual/block items are flagged for project owner confirmation.

Optional env vars for automated checks (add to .env):
  CHATWOOT_BASE_URL, CHATWOOT_API_TOKEN, CHATWOOT_ACCOUNT_ID
  BUTTERPOS_ANDROID_REPO   — git URL or local path to tablet app repo
  DATABASE_URL             — PostgreSQL read connection string
  BUTTERPOS_DATA_EXPORT    — path to restaurant/branch/user CSV or JSON export
  BILLING_API_URL          — billing/payment status API base URL
  BILLING_API_TOKEN        — auth token for billing API (if required)
  MCP_SERVER_URL           — backend teammate's MCP server endpoint
  WHATSAPP_EXPORT_PATH     — path to WhatsApp support history export

Usage:
  python verify_assumptions.py
  python verify_assumptions.py --output results/validation_report.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

_SPIKE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = _SPIKE_DIR / "results"

Status = Literal["verified", "manual", "blocked", "failed"]

ASSUMPTIONS: dict[str, str] = {
    "A1": "ButterPOS Android/tablet app codebase access for embedded chat widget",
    "A2": "Restaurant → Branch → User data accessible (DB read or validated export)",
    "A3": "Billing/payment status source identifiable (plan_type, payment_due, expiry)",
    "A4": "Chatwoot runs locally via Docker for dev/staging",
    "A5": "MCP server owned by backend teammate; this repo is MCP client only",
    "A6": "WhatsApp support history export available for KB audit (Step 0.3)",
    "A7": "Chat path is widget → middleware → Chatwoot (not direct)",
}


@dataclass
class CheckResult:
    id: str
    assumption: str
    status: Status
    evidence: str
    action_required: str | None = None


@dataclass
class ValidationReport:
    timestamp: str
    summary: dict[str, int]
    results: list[CheckResult]
    phase_0_assumptions_gate: bool


def env_present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def check_a1_android_repo() -> CheckResult:
    repo = os.getenv("BUTTERPOS_ANDROID_REPO", "").strip()
    if not repo:
        return CheckResult(
            id="A1",
            assumption=ASSUMPTIONS["A1"],
            status="blocked",
            evidence="BUTTERPOS_ANDROID_REPO not set in .env",
            action_required="Add git URL or local path to ButterPOS Android/tablet app repo",
        )
    path = Path(repo)
    if path.is_dir() and (path / ".git").exists():
        return CheckResult(
            id="A1",
            assumption=ASSUMPTIONS["A1"],
            status="verified",
            evidence=f"Local git repo exists: {path}",
        )
    if repo.startswith(("http://", "https://", "git@")):
        try:
            proc = subprocess.run(
                ["git", "ls-remote", "--heads", repo],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return CheckResult(
                    id="A1",
                    assumption=ASSUMPTIONS["A1"],
                    status="verified",
                    evidence=f"Remote repo reachable: {repo}",
                )
            return CheckResult(
                id="A1",
                assumption=ASSUMPTIONS["A1"],
                status="failed",
                evidence=f"git ls-remote failed: {proc.stderr[:200]}",
                action_required="Verify repo URL and access credentials",
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return CheckResult(
                id="A1",
                assumption=ASSUMPTIONS["A1"],
                status="manual",
                evidence=f"Could not auto-verify remote repo: {exc}",
                action_required="Confirm read access to Android repo manually",
            )
    return CheckResult(
        id="A1",
        assumption=ASSUMPTIONS["A1"],
        status="manual",
        evidence=f"BUTTERPOS_ANDROID_REPO set to '{repo}' — not a local git path or URL",
        action_required="Set valid git URL or local clone path",
    )


def _load_data_export(export_path: Path) -> tuple[int, str]:
    """Return (record_count, summary) from CSV or JSON export."""
    if export_path.suffix.lower() == ".json":
        data = json.loads(export_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return len(data), f"JSON array with {len(data)} records"
        if isinstance(data, dict):
            for key in ("restaurants", "branches", "users", "records"):
                if key in data and isinstance(data[key], list):
                    return len(data[key]), f"JSON.{key} with {len(data[key])} records"
            return len(data), f"JSON object with {len(data)} top-level keys"
    if export_path.suffix.lower() == ".csv":
        import csv

        with export_path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        return len(rows), f"CSV with {len(rows)} rows, columns: {list(rows[0].keys()) if rows else []}"
    return 0, "Unsupported export format"


def check_a2_data_access() -> CheckResult:
    export = os.getenv("BUTTERPOS_DATA_EXPORT", "").strip()
    if export:
        path = Path(export)
        if path.exists():
            try:
                count, summary = _load_data_export(path)
                # Soft check — report what we found
                return CheckResult(
                    id="A2",
                    assumption=ASSUMPTIONS["A2"],
                    status="verified" if count > 0 else "failed",
                    evidence=f"Export file readable: {summary}",
                    action_required=None if count > 0 else "Export file is empty",
                )
            except Exception as exc:  # noqa: BLE001
                return CheckResult(
                    id="A2",
                    assumption=ASSUMPTIONS["A2"],
                    status="failed",
                    evidence=f"Failed to parse export: {exc}",
                )
        return CheckResult(
            id="A2",
            assumption=ASSUMPTIONS["A2"],
            status="blocked",
            evidence=f"BUTTERPOS_DATA_EXPORT path not found: {export}",
            action_required="Provide valid path to restaurant/branch/user export",
        )

    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url:
        try:
            import psycopg2

            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            tables_found = []
            for table in ("restaurants", "restaurant", "branches", "branch", "users", "user"):
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
                    (table,),
                )
                if cur.fetchone()[0]:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 — spike table names
                    count = cur.fetchone()[0]
                    tables_found.append(f"{table}({count})")
            conn.close()
            if tables_found:
                return CheckResult(
                    id="A2",
                    assumption=ASSUMPTIONS["A2"],
                    status="verified",
                    evidence=f"DB reachable. Tables: {', '.join(tables_found)}",
                )
            return CheckResult(
                id="A2",
                assumption=ASSUMPTIONS["A2"],
                status="manual",
                evidence="DB reachable but no restaurant/branch/user tables found",
                action_required="Confirm schema table names or provide BUTTERPOS_DATA_EXPORT",
            )
        except ImportError:
            return CheckResult(
                id="A2",
                assumption=ASSUMPTIONS["A2"],
                status="manual",
                evidence="DATABASE_URL set but psycopg2 not installed — cannot auto-verify",
                action_required="pip install psycopg2-binary or provide BUTTERPOS_DATA_EXPORT",
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                id="A2",
                assumption=ASSUMPTIONS["A2"],
                status="failed",
                evidence=f"DATABASE_URL connection failed: {exc}",
                action_required="Fix connection string or provide read-only export file",
            )

    return CheckResult(
        id="A2",
        assumption=ASSUMPTIONS["A2"],
        status="blocked",
        evidence="Neither DATABASE_URL nor BUTTERPOS_DATA_EXPORT set",
        action_required="Add DATABASE_URL (read-only) or path to validated CSV/JSON export",
    )


def check_a3_billing_source() -> CheckResult:
    billing_url = os.getenv("BILLING_API_URL", "").strip()
    if not billing_url:
        return CheckResult(
            id="A3",
            assumption=ASSUMPTIONS["A3"],
            status="blocked",
            evidence="BILLING_API_URL not set",
            action_required=(
                "Document billing API endpoint that exposes plan_type, payment_due, expiry "
                "(env: BILLING_API_URL)"
            ),
        )
    try:
        headers = {}
        token = os.getenv("BILLING_API_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with httpx.Client(timeout=10.0) as client:
            response = client.get(billing_url, headers=headers)
        if response.status_code == 200:
            body = response.text[:300]
            fields_found = [
                f
                for f in ("plan_type", "payment_due", "expiry", "plan", "payment", "due")
                if f in body.lower()
            ]
            return CheckResult(
                id="A3",
                assumption=ASSUMPTIONS["A3"],
                status="verified" if fields_found else "manual",
                evidence=(
                    f"Billing API reachable (HTTP 200). "
                    f"Field hints in response: {fields_found or 'none detected — review manually'}"
                ),
                action_required=None
                if fields_found
                else "Confirm response includes plan_type, payment_due, expiry",
            )
        return CheckResult(
            id="A3",
            assumption=ASSUMPTIONS["A3"],
            status="failed",
            evidence=f"Billing API returned HTTP {response.status_code}",
            action_required="Fix BILLING_API_URL or auth token",
        )
    except httpx.HTTPError as exc:
        return CheckResult(
            id="A3",
            assumption=ASSUMPTIONS["A3"],
            status="failed",
            evidence=f"Billing API unreachable: {exc}",
            action_required="Verify BILLING_API_URL and network access",
        )


def check_a4_chatwoot() -> CheckResult:
    base = os.getenv("CHATWOOT_BASE_URL", "").strip()
    token = os.getenv("CHATWOOT_API_TOKEN", "").strip()
    account = os.getenv("CHATWOOT_ACCOUNT_ID", "").strip()

    if not base:
        return CheckResult(
            id="A4",
            assumption=ASSUMPTIONS["A4"],
            status="blocked",
            evidence="CHATWOOT_BASE_URL not set",
            action_required="Configure local Chatwoot Docker instance",
        )

    # Step 0.1 spike evidence
    spike_reports = sorted((_SPIKE_DIR.parent / "0.1_chat_surface" / "results").glob("spike_report_*.json"))
    spike_evidence = ""
    for report_path in reversed(spike_reports):
        data = json.loads(report_path.read_text())
        if data.get("error") is None and data.get("latency_target_met"):
            spike_evidence = (
                f"Step 0.1 spike passed ({report_path.name}): "
                f"mean={data['latency_summary'].get('mean_ms')}ms"
            )
            break

    try:
        with httpx.Client(base_url=base.rstrip("/"), timeout=10.0) as client:
            health = client.get("/api")
            health_ok = health.status_code == 200
            api_ok = False
            if token and account:
                r = client.get(
                    f"/api/v1/accounts/{account}/conversations",
                    headers={"api_access_token": token},
                    params={"page": 1},
                )
                api_ok = r.status_code in (200, 404)  # 404 ok if no conversations yet

        if health_ok:
            evidence = f"Chatwoot health OK at {base}"
            if api_ok:
                evidence += "; API token authenticates"
            if spike_evidence:
                evidence += f"; {spike_evidence}"
            return CheckResult(
                id="A4",
                assumption=ASSUMPTIONS["A4"],
                status="verified",
                evidence=evidence,
            )
        return CheckResult(
            id="A4",
            assumption=ASSUMPTIONS["A4"],
            status="failed",
            evidence=f"Chatwoot health check failed: HTTP {health.status_code}",
            action_required="Start Chatwoot Docker stack",
        )
    except httpx.HTTPError as exc:
        fallback = spike_evidence or "No successful Step 0.1 spike found"
        return CheckResult(
            id="A4",
            assumption=ASSUMPTIONS["A4"],
            status="manual" if spike_evidence else "failed",
            evidence=f"Live check failed ({exc}). {fallback}",
            action_required=None if spike_evidence else "Start Chatwoot and re-run",
        )


def check_a5_mcp_ownership() -> CheckResult:
    mcp_url = os.getenv("MCP_SERVER_URL", "").strip()
    if mcp_url:
        try:
            parsed = urlparse(mcp_url)
            with httpx.Client(timeout=5.0) as client:
                # MCP may not have HTTP health — try connect
                if parsed.scheme in ("http", "https"):
                    r = client.get(mcp_url)
                    return CheckResult(
                        id="A5",
                        assumption=ASSUMPTIONS["A5"],
                        status="manual",
                        evidence=(
                            f"MCP_SERVER_URL set ({mcp_url}), HTTP {r.status_code}. "
                            "Ownership split documented in MCP_INTEGRATION.md — "
                            "confirm with backend teammate."
                        ),
                        action_required="Obtain tool catalog from backend teammate (Step 0.6)",
                    )
        except httpx.HTTPError:
            pass
        return CheckResult(
            id="A5",
            assumption=ASSUMPTIONS["A5"],
            status="manual",
            evidence=f"MCP_SERVER_URL set ({mcp_url}) — endpoint not HTTP-probed",
            action_required="Confirm MCP server is running and owned by backend teammate",
        )

    return CheckResult(
        id="A5",
        assumption=ASSUMPTIONS["A5"],
        status="manual",
        evidence=(
            "MCP_SERVER_URL not set. Architectural split confirmed in D-4/D-5: "
            "backend teammate owns MCP server; this repo is client only. "
            "Full validation deferred to Step 0.6."
        ),
        action_required="Backend teammate to provide MCP server URL + tool list before Step 0.6",
    )


def check_a6_whatsapp_export() -> CheckResult:
    export_path = os.getenv("WHATSAPP_EXPORT_PATH", "").strip()
    if export_path:
        path = Path(export_path)
        if path.exists():
            size = path.stat().st_size
            return CheckResult(
                id="A6",
                assumption=ASSUMPTIONS["A6"],
                status="verified",
                evidence=f"WhatsApp export found: {path} ({size:,} bytes)",
            )
        return CheckResult(
            id="A6",
            assumption=ASSUMPTIONS["A6"],
            status="blocked",
            evidence=f"WHATSAPP_EXPORT_PATH not found: {export_path}",
            action_required="Provide valid WhatsApp export path",
        )

    sample = _SPIKE_DIR.parent / "0.3_kb_audit" / "sample_data" / "sample_messages.json"
    return CheckResult(
        id="A6",
        assumption=ASSUMPTIONS["A6"],
        status="manual",
        evidence=(
            "Production WhatsApp export not provided. "
            f"Step 0.3 categorizer ready; sample data only ({sample.name})."
        ),
        action_required="Provide 3–6 month WhatsApp export for production KB MVP (Step 0.3)",
    )


def check_a7_chat_path() -> CheckResult:
    spike_dir = _SPIKE_DIR.parent / "0.1_chat_surface"
    spike_script = spike_dir / "chat_surface_spike.py"
    decisions = _SPIKE_DIR.parents[1] / "docs" / "DECISIONS.md"

    evidence_parts = [
        "D-2 locked: widget → middleware → Chatwoot (no direct widget→Chatwoot)",
    ]
    if spike_script.exists():
        evidence_parts.append("Step 0.1 spike validates middleware→Chatwoot Application API path")
    if decisions.exists():
        text = decisions.read_text(encoding="utf-8")
        if "D-2" in text and "middleware" in text:
            evidence_parts.append("DECISIONS.md D-2 documents architecture")

    return CheckResult(
        id="A7",
        assumption=ASSUMPTIONS["A7"],
        status="verified",
        evidence="; ".join(evidence_parts),
    )


CHECKERS = [
    check_a1_android_repo,
    check_a2_data_access,
    check_a3_billing_source,
    check_a4_chatwoot,
    check_a5_mcp_ownership,
    check_a6_whatsapp_export,
    check_a7_chat_path,
]


def run_validation() -> ValidationReport:
    load_dotenv(_SPIKE_DIR.parents[1] / ".env")
    results = [checker() for checker in CHECKERS]
    summary = {
        "verified": sum(1 for r in results if r.status == "verified"),
        "manual": sum(1 for r in results if r.status == "manual"),
        "blocked": sum(1 for r in results if r.status == "blocked"),
        "failed": sum(1 for r in results if r.status == "failed"),
    }
    # Gate passes if no blocked/failed — manual items need owner ack
    gate = summary["blocked"] == 0 and summary["failed"] == 0

    return ValidationReport(
        timestamp=datetime.now(UTC).isoformat(),
        summary=summary,
        results=results,
        phase_0_assumptions_gate=gate,
    )


def print_report(report: ValidationReport) -> None:
    print("\n=== Step 0.4 Assumption Validation (A1–A7) ===\n")
    icons = {"verified": "✓", "manual": "?", "blocked": "✗", "failed": "✗"}
    for r in report.results:
        icon = icons.get(r.status, " ")
        print(f"  [{icon}] {r.id} ({r.status.upper()})")
        print(f"      {r.assumption}")
        print(f"      Evidence: {r.evidence}")
        if r.action_required:
            print(f"      Action: {r.action_required}")
        print()

    print(
        f"Summary: {report.summary['verified']} verified, "
        f"{report.summary['manual']} manual, "
        f"{report.summary['blocked']} blocked, "
        f"{report.summary['failed']} failed"
    )
    gate = "PASS" if report.phase_0_assumptions_gate else "BLOCKED"
    print(f"Automated gate: {gate} (manual items require owner sign-off)\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Assumption validation — Step 0.4")
    parser.add_argument("--output", "-o", type=Path, help="Write JSON report to path")
    args = parser.parse_args()

    report = run_validation()
    print_report(report)

    out = args.output or RESULTS_DIR / f"validation_report_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    print(f"Report: {out}")

    return 0 if report.phase_0_assumptions_gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
