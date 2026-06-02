#!/usr/bin/env python3
"""Live ChatwootAdapter integration — Phase 1 exit Task 1.8.2."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings, get_settings
from app.models.standard import (
    AddCommentRequest,
    AddNoteRequest,
    AddTagsRequest,
    AssignAgentRequest,
    CreateContactRequest,
    CreateTicketRequest,
    StandardStatus,
    UpdateStatusRequest,
)
from app.providers.ticketing.chatwoot.auth import missing_config_fields
from app.providers.ticketing.chatwoot_adapter import ChatwootAdapter


@dataclass
class ValidationCheck:
    name: str
    passed: bool
    detail: str


@dataclass
class ValidationReport:
    passed: bool
    checks: list[ValidationCheck]
    contact_id: str | None = None
    ticket_id: str | None = None



async def validate_adapter(settings: Settings) -> ValidationReport:
    """Exercise ChatwootAdapter methods against live Chatwoot."""
    checks: list[ValidationCheck] = []
    contact_id: str | None = None
    ticket_id: str | None = None
    suffix = uuid.uuid4().hex[:8]

    adapter = ChatwootAdapter(settings)
    try:
        health = await adapter.health_check()
        checks.append(
            ValidationCheck(
                name="health_check",
                passed=health.healthy,
                detail=f"provider={health.provider} latency_ms={health.latency_ms} msg={health.message}",
            ),
        )
        if not health.healthy:
            return ValidationReport(passed=False, checks=checks)

        contact = await adapter.get_or_create_contact(
            CreateContactRequest(
                name=f"ButterPOS Integration {suffix}",
                external_user_id=f"butterpos-integration-{suffix}",
                metadata={"integration_test": True},
            ),
        )
        contact_id = contact.provider_contact_id
        checks.append(
            ValidationCheck(
                name="get_or_create_contact",
                passed=bool(contact_id),
                detail=f"contact_id={contact_id}",
            ),
        )

        ticket = await adapter.create_ticket(
            CreateTicketRequest(
                provider_contact_id=contact_id,
                subject=f"Integration test {suffix}",
                initial_message="Automated ChatwootAdapter validation message.",
                tags=["butterpos-integration"],
                metadata={"source_id": f"integration-{suffix}"},
            ),
        )
        ticket_id = ticket.provider_ticket_id
        checks.append(
            ValidationCheck(
                name="create_ticket",
                passed=bool(ticket_id) and ticket.status is StandardStatus.OPEN,
                detail=f"ticket_id={ticket_id} status={ticket.status.value}",
            ),
        )

        fetched = await adapter.get_ticket(ticket_id)
        checks.append(
            ValidationCheck(
                name="get_ticket",
                passed=fetched.provider_ticket_id == ticket_id,
                detail=f"status={fetched.status.value}",
            ),
        )

        await adapter.add_comment(
            AddCommentRequest(
                provider_ticket_id=ticket_id,
                body="Public integration test reply from middleware.",
            ),
        )
        checks.append(ValidationCheck(name="add_comment", passed=True, detail="ok"))

        await adapter.add_note(
            AddNoteRequest(
                provider_ticket_id=ticket_id,
                body="Private integration test note.",
            ),
        )
        checks.append(ValidationCheck(name="add_note", passed=True, detail="ok"))

        tagged = await adapter.add_tags(
            AddTagsRequest(provider_ticket_id=ticket_id, tags=["integration-pass"]),
        )
        checks.append(
            ValidationCheck(
                name="add_tags",
                passed="integration-pass" in tagged.tags,
                detail=f"tags={tagged.tags}",
            ),
        )

        in_progress = await adapter.update_status(
            UpdateStatusRequest(
                provider_ticket_id=ticket_id,
                status=StandardStatus.IN_PROGRESS,
            ),
        )
        checks.append(
            ValidationCheck(
                name="update_status",
                passed=in_progress.status is StandardStatus.IN_PROGRESS,
                detail=f"status={in_progress.status.value}",
            ),
        )

        agent_id = settings.chatwoot_agent_id.strip()
        if agent_id:
            assigned = await adapter.assign_agent(
                AssignAgentRequest(provider_ticket_id=ticket_id, assignee_id=agent_id),
            )
            checks.append(
                ValidationCheck(
                    name="assign_agent",
                    passed=assigned.assignee_id == agent_id,
                    detail=f"assignee_id={assigned.assignee_id}",
                ),
            )
        else:
            checks.append(
                ValidationCheck(
                    name="assign_agent",
                    passed=True,
                    detail="skipped — set CHATWOOT_AGENT_ID to test assignment",
                ),
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(ValidationCheck(name="unexpected_error", passed=False, detail=str(exc)))
    finally:
        await adapter._client.close()

    passed = all(check.passed for check in checks)
    return ValidationReport(passed=passed, checks=checks, contact_id=contact_id, ticket_id=ticket_id)


def _middleware_ticketing_health(base_url: str, client_id: str, client_secret: str) -> ValidationCheck:
    try:
        with httpx.Client(base_url=base_url.rstrip("/"), timeout=15.0) as client:
            token_resp = client.post(
                "/api/v1/auth/token",
                json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "subject": "chatwoot-validation",
                },
            )
            if token_resp.status_code != 200:
                return ValidationCheck(
                    name="middleware_ticketing_health",
                    passed=False,
                    detail=f"token HTTP {token_resp.status_code}",
                )
            token = token_resp.json()["access_token"]
            health = client.get(
                "/api/v1/system/ticketing-health",
                headers={"Authorization": f"Bearer {token}"},
            )
            if health.status_code != 200:
                return ValidationCheck(
                    name="middleware_ticketing_health",
                    passed=False,
                    detail=f"HTTP {health.status_code}",
                )
            body = health.json()
            return ValidationCheck(
                name="middleware_ticketing_health",
                passed=body.get("healthy") is True,
                detail=f"provider={body.get('provider')} latency_ms={body.get('latency_ms')}",
            )
    except httpx.ConnectError as exc:
        return ValidationCheck(
            name="middleware_ticketing_health",
            passed=False,
            detail=f"connect failed: {exc}",
        )


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Live ChatwootAdapter validation")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable report")
    parser.add_argument(
        "--middleware-url",
        default="",
        help="Optional running middleware URL for /ticketing-health probe",
    )
    args = parser.parse_args()

    get_settings.cache_clear()
    settings = get_settings()
    middleware_url = args.middleware_url or settings.middleware_base_url

    config_missing = missing_config_fields(settings)
    if not settings.chatwoot_inbox_id:
        config_missing.append("CHATWOOT_INBOX_ID")
    if config_missing:
        print("Missing Chatwoot config:", ", ".join(config_missing), file=sys.stderr)
        return 1

    report = asyncio.run(validate_adapter(settings))

    if middleware_url and settings.api_client_id and settings.api_client_secret:
        report.checks.append(
            _middleware_ticketing_health(
                middleware_url,
                settings.api_client_id,
                settings.api_client_secret,
            ),
        )
        report.passed = all(check.passed for check in report.checks)

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print("=== ChatwootAdapter validation (Task 1.8.2) ===\n")
        for check in report.checks:
            status = "OK" if check.passed else "FAIL"
            print(f"  [{status}] {check.name}: {check.detail}")
        if report.contact_id or report.ticket_id:
            print(f"\nArtifacts: contact_id={report.contact_id} ticket_id={report.ticket_id}")
        print()
        print("RESULT:", "PASS" if report.passed else "FAIL")

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
