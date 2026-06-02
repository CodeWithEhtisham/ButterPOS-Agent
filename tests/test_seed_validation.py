"""Seed validation tests — Task 1.7.2 (offline mapping checks against fixture data)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.customer_mapping import CustomerMappingResult, MappingStatus
from app.repositories.customer_mapping_repository import MappingRecord
from app.services.customer_mapping_service import CustomerMappingService
from app.services.tenant_validation_service import DEMO_USER_EXPECTATIONS, validate_seeded_data

NOW = datetime(2026, 6, 2, 6, 0, tzinfo=UTC)


def _demo_record(user_id: str) -> MappingRecord:
    if user_id == "demo-user-active":
        return MappingRecord(
            butterpos_user_id=user_id,
            user_id=1,
            language_pref="roman_ur",
            provider_contact_id="9001",
            branch_id=10,
            butterpos_branch_id="demo-branch-karachi",
            branch_name="Karachi Main",
            branch_timezone="Asia/Karachi",
            restaurant_id=20,
            butterpos_restaurant_id="demo-rest-active",
            restaurant_name="Demo Dhaba",
            plan_type="8h",
            payment_due=False,
            plan_expiry=datetime(2027, 12, 31, tzinfo=UTC),
            sla_coverage_hours=8,
            sla_first_response_minutes=30,
            sla_resolution_minutes=240,
            sla_escalation_after_minutes=120,
            sla_rules={"coverage_start_hour": 9},
            sla_is_active=True,
        )
    if user_id == "demo-user-unpaid":
        return MappingRecord(
            butterpos_user_id=user_id,
            user_id=2,
            language_pref="en",
            provider_contact_id="9002",
            branch_id=11,
            butterpos_branch_id="demo-branch-lahore",
            branch_name="Lahore Mall",
            branch_timezone="Asia/Karachi",
            restaurant_id=21,
            butterpos_restaurant_id="demo-rest-unpaid",
            restaurant_name="Demo Cafe",
            plan_type="16h",
            payment_due=True,
            plan_expiry=datetime(2027, 12, 31, tzinfo=UTC),
            sla_coverage_hours=16,
            sla_first_response_minutes=20,
            sla_resolution_minutes=180,
            sla_escalation_after_minutes=90,
            sla_rules={"coverage_start_hour": 8},
            sla_is_active=True,
        )
    return MappingRecord(
        butterpos_user_id=user_id,
        user_id=3,
        language_pref="en",
        provider_contact_id=None,
        branch_id=None,
        butterpos_branch_id=None,
        branch_name=None,
        branch_timezone=None,
        restaurant_id=None,
        butterpos_restaurant_id=None,
        restaurant_name=None,
        plan_type=None,
        payment_due=None,
        plan_expiry=None,
        sla_coverage_hours=None,
        sla_first_response_minutes=None,
        sla_resolution_minutes=None,
        sla_escalation_after_minutes=None,
        sla_rules=None,
        sla_is_active=None,
    )


def test_demo_fixture_mapping_expectations() -> None:
    async def _run() -> None:
        session = MagicMock()

        async def _get_user(user_id: str) -> MappingRecord | None:
            if user_id in DEMO_USER_EXPECTATIONS:
                return _demo_record(user_id)
            return None

        service = CustomerMappingService(session)
        service._repo.get_by_butterpos_user_id = AsyncMock(side_effect=_get_user)

        for user_id, expected in DEMO_USER_EXPECTATIONS.items():
            result = await service.resolve_by_user_id(user_id, now=NOW)
            assert result.status is expected, f"{user_id}: {result.status}"

    asyncio.run(_run())


def test_validate_seeded_data_report() -> None:
    async def _run() -> None:
        session = MagicMock()

        async def _scalar(stmt: object) -> int:
            sql = str(stmt)
            if "restaurants" in sql:
                return 3
            if "branches" in sql:
                return 2
            if "users" in sql:
                return 3
            if "sla_config" in sql:
                return 3
            return 0

        session.scalar = AsyncMock(side_effect=_scalar)

        async def _resolve_user(user_id: str, *, now: datetime | None = None) -> CustomerMappingResult:
            del now
            if user_id == "does-not-exist":
                return CustomerMappingResult(
                    status=MappingStatus.UNKNOWN_USER,
                    status_message="missing",
                    max_agent_tier=1,
                    butterpos_user_id=user_id,
                )
            expected = DEMO_USER_EXPECTATIONS[user_id]
            return CustomerMappingResult(
                status=expected,
                status_message="ok",
                max_agent_tier=1 if expected is not MappingStatus.ACTIVE else 3,
                butterpos_user_id=user_id,
            )

        async def _resolve_contact(contact_id: str, *, now: datetime | None = None) -> CustomerMappingResult:
            del now
            mapping = {"9001": MappingStatus.ACTIVE, "9002": MappingStatus.PAYMENT_DUE}
            status = mapping[contact_id]
            return CustomerMappingResult(
                status=status,
                status_message="ok",
                max_agent_tier=3 if status is MappingStatus.ACTIVE else 1,
                provider_contact_id=contact_id,
            )

        mapper = MagicMock()
        mapper.resolve_by_user_id = AsyncMock(side_effect=_resolve_user)
        mapper.resolve_by_contact_id = AsyncMock(side_effect=_resolve_contact)

        with patch(
            "app.services.tenant_validation_service.CustomerMappingService",
            return_value=mapper,
        ):
            report = await validate_seeded_data(session, now=NOW)

        assert report.passed is True
        assert len(report.checks) >= 10

    asyncio.run(_run())
