#!/usr/bin/env python3
"""
Step 0.1 — Chat surface spike harness.

Simulates: tablet widget → stub middleware → Chatwoot (Application API).

Measures round-trip latency (post message → read back) and probes rich-UI
content types supported on an API-channel inbox.

Required env vars (add to .env — never commit real values):
  CHATWOOT_BASE_URL       e.g. http://localhost:3000
  CHATWOOT_API_TOKEN      Profile → Access Token
  CHATWOOT_ACCOUNT_ID     Numeric account ID
  CHATWOOT_INBOX_ID       API-channel inbox ID

Usage:
  python spikes/0.1_chat_surface/chat_surface_spike.py
  python spikes/0.1_chat_surface/chat_surface_spike.py --rounds 5
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

RESULTS_DIR = Path(__file__).resolve().parent / "results"
LATENCY_TARGET_MS = 5000  # board target from Step 0.1


@dataclass
class SpikeConfig:
    base_url: str
    api_token: str
    account_id: int
    inbox_id: int
    rounds: int = 3


@dataclass
class LatencyResult:
    round_num: int
    post_ms: float
    read_back_ms: float
    total_ms: float
    message_id: int | None


@dataclass
class CapabilityResult:
    feature: str
    content_type: str
    status: str  # pass | fail | skip
    notes: str
    message_id: int | None = None


@dataclass
class SpikeReport:
    timestamp: str
    config_summary: dict[str, Any]
    latency: list[LatencyResult] = field(default_factory=list)
    latency_summary: dict[str, Any] = field(default_factory=dict)
    capabilities: list[CapabilityResult] = field(default_factory=list)
    latency_target_ms: int = LATENCY_TARGET_MS
    latency_target_met: bool | None = None
    error: str | None = None


def load_config(rounds: int) -> SpikeConfig:
    load_dotenv()
    missing = [
        name
        for name in (
            "CHATWOOT_BASE_URL",
            "CHATWOOT_API_TOKEN",
            "CHATWOOT_ACCOUNT_ID",
            "CHATWOOT_INBOX_ID",
        )
        if not os.getenv(name)
    ]
    if missing:
        raise SystemExit(
            "Missing required env vars: "
            + ", ".join(missing)
            + "\nAdd them to .env (see spikes/0.1_chat_surface/README.md)."
        )
    return SpikeConfig(
        base_url=os.environ["CHATWOOT_BASE_URL"].rstrip("/"),
        api_token=os.environ["CHATWOOT_API_TOKEN"],
        account_id=int(os.environ["CHATWOOT_ACCOUNT_ID"]),
        inbox_id=int(os.environ["CHATWOOT_INBOX_ID"]),
        rounds=rounds,
    )


def client_for(config: SpikeConfig) -> httpx.Client:
    return httpx.Client(
        base_url=config.base_url,
        headers={
            "api_access_token": config.api_token,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def check_health(client: httpx.Client) -> None:
    response = client.get("/api")
    response.raise_for_status()


def create_contact(client: httpx.Client, config: SpikeConfig) -> int:
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "name": f"Spike Test {suffix}",
        "identifier": f"butterpos-spike-{suffix}",
    }
    response = client.post(
        f"/api/v1/accounts/{config.account_id}/contacts",
        json={"inbox_id": config.inbox_id, **payload},
    )
    response.raise_for_status()
    data = response.json()
    contact_id = data.get("payload", data).get("contact", data).get("id")
    if contact_id is None:
        contact_id = data.get("id")
    if contact_id is None:
        raise RuntimeError(f"Could not parse contact id from: {data}")
    return int(contact_id)


def create_conversation(
    client: httpx.Client, config: SpikeConfig, contact_id: int
) -> int:
    source_id = f"spike-{uuid.uuid4().hex}"
    payload = {
        "source_id": source_id,
        "inbox_id": config.inbox_id,
        "contact_id": contact_id,
        "status": "open",
    }
    response = client.post(
        f"/api/v1/accounts/{config.account_id}/conversations",
        json=payload,
    )
    response.raise_for_status()
    data = response.json()
    conversation_id = data.get("id")
    if conversation_id is None:
        raise RuntimeError(f"Could not parse conversation id from: {data}")
    return int(conversation_id)


def post_message(
    client: httpx.Client,
    config: SpikeConfig,
    conversation_id: int,
    *,
    content: str,
    content_type: str = "text",
    content_attributes: dict[str, Any] | None = None,
) -> tuple[int, float]:
    payload: dict[str, Any] = {
        "content": content,
        "message_type": "outgoing",
        "content_type": content_type,
        "private": False,
    }
    if content_attributes:
        payload["content_attributes"] = content_attributes
    start = time.perf_counter()
    response = client.post(
        f"/api/v1/accounts/{config.account_id}/conversations/{conversation_id}/messages",
        json=payload,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.raise_for_status()
    data = response.json()
    message_id = data.get("id")
    return int(message_id), elapsed_ms


def read_messages(
    client: httpx.Client,
    config: SpikeConfig,
    conversation_id: int,
    *,
    expected_message_id: int | None = None,
) -> tuple[bool, float]:
    start = time.perf_counter()
    for _ in range(10):
        response = client.get(
            f"/api/v1/accounts/{config.account_id}/conversations/{conversation_id}/messages"
        )
        response.raise_for_status()
        payload = response.json()
        messages = payload.get("payload", payload)
        if isinstance(messages, dict):
            messages = messages.get("messages", [])
        ids = {m.get("id") for m in messages}
        if expected_message_id is None or expected_message_id in ids:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return True, elapsed_ms
        time.sleep(0.2)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return False, elapsed_ms


def run_latency_rounds(
    client: httpx.Client,
    config: SpikeConfig,
    conversation_id: int,
) -> list[LatencyResult]:
    results: list[LatencyResult] = []
    for i in range(1, config.rounds + 1):
        content = f"[spike round {i}] ButterPOS middleware ping {uuid.uuid4().hex[:6]}"
        message_id, post_ms = post_message(
            client, config, conversation_id, content=content
        )
        found, read_ms = read_messages(
            client, config, conversation_id, expected_message_id=message_id
        )
        total_ms = post_ms + read_ms
        results.append(
            LatencyResult(
                round_num=i,
                post_ms=round(post_ms, 2),
                read_back_ms=round(read_ms, 2),
                total_ms=round(total_ms, 2),
                message_id=message_id if found else None,
            )
        )
    return results


def probe_capabilities(
    client: httpx.Client,
    config: SpikeConfig,
    conversation_id: int,
) -> list[CapabilityResult]:
    probes: list[tuple[str, str, dict[str, Any] | None, str]] = [
        (
            "Plain text message",
            "text",
            None,
            "Baseline outgoing text via Application API.",
        ),
        (
            "Quick replies (input_select)",
            "input_select",
            {
                "items": [
                    {"title": "Printer issue", "value": "printer"},
                    {"title": "Sync stuck", "value": "sync"},
                ]
            },
            "Chatwoot Web Widget / API channel interactive select.",
        ),
        (
            "Action buttons (cards postback)",
            "cards",
            {
                "items": [
                    {
                        "title": "Restart printer",
                        "description": "Run printer diagnostic",
                        "actions": [
                            {
                                "type": "postback",
                                "text": "Restart",
                                "payload": "RESTART_PRINTER",
                            }
                        ],
                    }
                ]
            },
            "Card with postback action — middleware receives selection via webhook.",
        ),
        (
            "Inline form",
            "form",
            {
                "items": [
                    {
                        "name": "branch_id",
                        "type": "text",
                        "label": "Branch ID",
                        "placeholder": "Enter branch ID",
                    }
                ]
            },
            "Structured input collection in widget.",
        ),
    ]

    results: list[CapabilityResult] = []
    for feature, content_type, attrs, notes in probes:
        try:
            message_id, _ = post_message(
                client,
                config,
                conversation_id,
                content=f"[capability probe] {feature}",
                content_type=content_type,
                content_attributes=attrs,
            )
            found, _ = read_messages(
                client, config, conversation_id, expected_message_id=message_id
            )
            status = "pass" if found else "fail"
            detail = notes if found else f"{notes} Message not readable after post."
        except httpx.HTTPStatusError as exc:
            status = "fail"
            message_id = None
            body = exc.response.text[:300]
            detail = f"HTTP {exc.response.status_code}: {body}"
        except Exception as exc:  # noqa: BLE001 — spike captures all probe failures
            status = "fail"
            message_id = None
            detail = str(exc)

        results.append(
            CapabilityResult(
                feature=feature,
                content_type=content_type,
                status=status,
                notes=detail,
                message_id=message_id,
            )
        )
    return results


def summarize_latency(results: list[LatencyResult]) -> dict[str, Any]:
    totals = [r.total_ms for r in results if r.message_id is not None]
    if not totals:
        return {"samples": 0, "error": "No successful round-trips"}
    return {
        "samples": len(totals),
        "min_ms": round(min(totals), 2),
        "max_ms": round(max(totals), 2),
        "mean_ms": round(statistics.mean(totals), 2),
        "median_ms": round(statistics.median(totals), 2),
        "target_ms": LATENCY_TARGET_MS,
        "target_met": all(t < LATENCY_TARGET_MS for t in totals),
    }


def write_report(report: SpikeReport) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"spike_report_{stamp}.json"
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return path


def print_summary(report: SpikeReport) -> None:
    print("\n=== Step 0.1 Chat Surface Spike ===\n")
    if report.error:
        print(f"ERROR: {report.error}\n")
        return
    print("Latency (post + read-back):")
    for row in report.latency:
        ok = "OK" if row.message_id else "MISS"
        print(
            f"  Round {row.round_num}: post={row.post_ms}ms read={row.read_back_ms}ms "
            f"total={row.total_ms}ms [{ok}]"
        )
    summary = report.latency_summary
    if summary.get("samples"):
        print(
            f"\n  Summary: mean={summary['mean_ms']}ms median={summary['median_ms']}ms "
            f"max={summary['max_ms']}ms target=<{LATENCY_TARGET_MS}ms "
            f"→ {'PASS' if summary.get('target_met') else 'FAIL'}"
        )
    print("\nCapability matrix:")
    for cap in report.capabilities:
        print(f"  [{cap.status.upper():4}] {cap.feature} ({cap.content_type})")
        if cap.status == "fail":
            print(f"         {cap.notes[:120]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chatwoot chat surface spike")
    parser.add_argument("--rounds", type=int, default=3, help="Latency test rounds")
    args = parser.parse_args()

    report = SpikeReport(
        timestamp=datetime.now(UTC).isoformat(),
        config_summary={},
    )

    try:
        config = load_config(args.rounds)
        report.config_summary = {
            "base_url": config.base_url,
            "account_id": config.account_id,
            "inbox_id": config.inbox_id,
            "rounds": config.rounds,
        }

        with client_for(config) as client:
            check_health(client)
            contact_id = create_contact(client, config)
            conversation_id = create_conversation(client, config, contact_id)
            report.config_summary["contact_id"] = contact_id
            report.config_summary["conversation_id"] = conversation_id

            report.latency = run_latency_rounds(client, config, conversation_id)
            report.latency_summary = summarize_latency(report.latency)
            report.latency_target_met = report.latency_summary.get("target_met")
            report.capabilities = probe_capabilities(client, config, conversation_id)

    except SystemExit as exc:
        report.error = str(exc)
        print(exc, file=sys.stderr)
    except httpx.HTTPError as exc:
        report.error = f"HTTP error: {exc}"
        print(report.error, file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — spike top-level catch for report
        report.error = str(exc)
        print(report.error, file=sys.stderr)

    path = write_report(report)
    print_summary(report)
    print(f"\nReport written to: {path}")
    return 0 if report.error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
