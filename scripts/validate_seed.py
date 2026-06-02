#!/usr/bin/env python3
"""Validate seeded tenant data and mapping scenarios — Task 1.7.2."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from app.core.config import get_settings
from app.db.session import get_session_factory, init_engine
from app.services.tenant_validation_service import validate_seeded_data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Postgres seed + mapping scenarios.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON report",
    )
    parser.add_argument(
        "--at",
        type=str,
        default="2026-06-02T06:00:00+00:00",
        help="ISO timestamp for coverage evaluation (default: within 8h Karachi window)",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    load_dotenv()
    settings = get_settings()
    now = datetime.fromisoformat(args.at.replace("Z", "+00:00"))
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    init_engine(settings)
    factory = get_session_factory()
    async with factory() as session:
        report = await validate_seeded_data(session, now=now)

    if args.json:
        payload = {
            "passed": report.passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail} for c in report.checks
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        print("=== Seed validation (Task 1.7.2) ===\n")
        for check in report.checks:
            mark = "OK" if check.passed else "FAIL"
            print(f"  [{mark}] {check.name}: {check.detail}")
        print()
        print("RESULT:", "PASS" if report.passed else "FAIL")

    return 0 if report.passed else 1


def main() -> int:
    return asyncio.run(_run(_build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
