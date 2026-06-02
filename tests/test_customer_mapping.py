"""Customer/branch mapping tests — Task 1.6 sub-step 2 (100% coverage gate)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.db.models.branch import Branch
from app.db.models.restaurant import Restaurant
from app.db.models.sla_config import SLAConfig
from app.db.models.user import User
from app.models.customer_mapping import MappingStatus
from app.repositories.customer_mapping_repository import (
    CustomerMappingRepository,
    MappingRecord,
    _row_to_record,
)
from app.services.customer_mapping_service import CustomerMappingService
from app.services.mapping.coverage import is_within_coverage_window
from app.services.mapping.evaluator import (
    evaluate_mapping_record,
    unknown_contact_result,
    unknown_user_result,
)
from app.services.mapping.plan_status import is_plan_expired

NOW = datetime(2026, 6, 2, 6, 0, tzinfo=UTC)  # 11:00 Asia/Karachi
OUTSIDE_8H = datetime(2026, 6, 2, 14, 0, tzinfo=UTC)  # 19:00 Asia/Karachi


def _record(**overrides: object) -> MappingRecord:
    defaults: dict[str, object] = {
        "butterpos_user_id": "staff-1",
        "user_id": 1,
        "language_pref": "en",
        "provider_contact_id": "101",
        "branch_id": 10,
        "butterpos_branch_id": "branch-1",
        "branch_name": "Main",
        "branch_timezone": "Asia/Karachi",
        "restaurant_id": 20,
        "butterpos_restaurant_id": "rest-1",
        "restaurant_name": "Test Restaurant",
        "plan_type": "8h",
        "payment_due": False,
        "plan_expiry": datetime(2027, 1, 1, tzinfo=UTC),
        "sla_coverage_hours": 8,
        "sla_first_response_minutes": 30,
        "sla_resolution_minutes": 240,
        "sla_escalation_after_minutes": 120,
        "sla_rules": {"coverage_start_hour": 9},
        "sla_is_active": True,
    }
    defaults.update(overrides)
    return MappingRecord(**defaults)  # type: ignore[arg-type]


# --- plan_status ---


def test_is_plan_expired_none_is_active() -> None:
    assert is_plan_expired(None, now=NOW) is False


def test_is_plan_expired_future() -> None:
    assert is_plan_expired(NOW + timedelta(days=1), now=NOW) is False


def test_is_plan_expired_past() -> None:
    assert is_plan_expired(NOW - timedelta(days=1), now=NOW) is True


def test_is_plan_expired_naive_datetimes() -> None:
    expiry = datetime(2025, 1, 1)
    now = datetime(2026, 1, 1)
    assert is_plan_expired(expiry, now=now) is True


# --- coverage ---


def test_coverage_8h_plan_within_window() -> None:
    assert (
        is_within_coverage_window(
            now_utc=NOW,
            branch_timezone="Asia/Karachi",
            coverage_hours=8,
            coverage_start_hour=9,
        )
        is True
    )


def test_coverage_8h_plan_outside_window() -> None:
    assert (
        is_within_coverage_window(
            now_utc=OUTSIDE_8H,
            branch_timezone="Asia/Karachi",
            coverage_hours=8,
            coverage_start_hour=9,
        )
        is False
    )


def test_coverage_16h_plan_within_window() -> None:
    noon_pkt = datetime(2026, 6, 2, 7, 0, tzinfo=UTC)  # 12:00 Asia/Karachi
    assert (
        is_within_coverage_window(
            now_utc=noon_pkt,
            branch_timezone="Asia/Karachi",
            coverage_hours=16,
            coverage_start_hour=8,
        )
        is True
    )


def test_coverage_16h_plan_outside_window() -> None:
    early = datetime(2026, 6, 2, 2, 0, tzinfo=UTC)  # 07:00 Asia/Karachi
    assert (
        is_within_coverage_window(
            now_utc=early,
            branch_timezone="Asia/Karachi",
            coverage_hours=16,
            coverage_start_hour=8,
        )
        is False
    )


def test_coverage_24_7_always_within() -> None:
    assert (
        is_within_coverage_window(
            now_utc=OUTSIDE_8H,
            branch_timezone="Asia/Karachi",
            coverage_hours=24,
        )
        is True
    )


def test_coverage_invalid_timezone_returns_false() -> None:
    assert (
        is_within_coverage_window(
            now_utc=NOW,
            branch_timezone="Not/A_Timezone",
            coverage_hours=8,
        )
        is False
    )


# --- evaluator ---


def test_unknown_user_result() -> None:
    result = unknown_user_result("missing-user")
    assert result.status is MappingStatus.UNKNOWN_USER
    assert result.max_agent_tier == 1
    assert result.butterpos_user_id == "missing-user"


def test_unknown_contact_result() -> None:
    result = unknown_contact_result("999")
    assert result.status is MappingStatus.UNKNOWN_USER
    assert result.provider_contact_id == "999"


def test_evaluate_active_8h_plan() -> None:
    result = evaluate_mapping_record(_record(plan_type="8h", sla_coverage_hours=8), now=NOW)
    assert result.status is MappingStatus.ACTIVE
    assert result.max_agent_tier == 3
    assert result.sla is not None
    assert result.sla.within_coverage is True
    assert result.sla.coverage_hours == 8


def test_evaluate_active_16h_plan() -> None:
    result = evaluate_mapping_record(
        _record(plan_type="16h", sla_coverage_hours=16, sla_rules={"coverage_start_hour": 8}),
        now=NOW,
    )
    assert result.status is MappingStatus.ACTIVE
    assert result.sla is not None
    assert result.sla.coverage_hours == 16


def test_evaluate_active_24_7_plan() -> None:
    result = evaluate_mapping_record(
        _record(plan_type="24-7", sla_coverage_hours=24),
        now=OUTSIDE_8H,
    )
    assert result.status is MappingStatus.ACTIVE
    assert result.sla is not None
    assert result.sla.within_coverage is True


def test_evaluate_no_branch() -> None:
    result = evaluate_mapping_record(_record(branch_id=None, branch_timezone=None), now=NOW)
    assert result.status is MappingStatus.NO_BRANCH
    assert result.max_agent_tier == 1


def test_evaluate_plan_expired() -> None:
    result = evaluate_mapping_record(
        _record(plan_expiry=NOW - timedelta(days=1)),
        now=NOW,
    )
    assert result.status is MappingStatus.PLAN_EXPIRED
    assert result.max_agent_tier == 1


def test_evaluate_payment_due() -> None:
    result = evaluate_mapping_record(_record(payment_due=True), now=NOW)
    assert result.status is MappingStatus.PAYMENT_DUE
    assert result.max_agent_tier == 1


def test_evaluate_outside_coverage() -> None:
    result = evaluate_mapping_record(_record(sla_coverage_hours=8), now=OUTSIDE_8H)
    assert result.status is MappingStatus.OUTSIDE_COVERAGE
    assert result.sla is not None
    assert result.sla.within_coverage is False


def test_evaluate_sla_not_configured_missing_hours() -> None:
    result = evaluate_mapping_record(_record(sla_coverage_hours=None), now=NOW)
    assert result.status is MappingStatus.SLA_NOT_CONFIGURED


def test_evaluate_sla_not_configured_inactive() -> None:
    result = evaluate_mapping_record(_record(sla_is_active=False), now=NOW)
    assert result.status is MappingStatus.SLA_NOT_CONFIGURED


def test_evaluate_coverage_start_hour_from_rules_and_invalid_rules() -> None:
    result = evaluate_mapping_record(
        _record(sla_rules={"coverage_start_hour": 7}),
        now=NOW,
    )
    assert result.sla is not None
    assert result.sla.coverage_start_hour == 7

    bad_rules = evaluate_mapping_record(
        _record(sla_rules={"coverage_start_hour": "bad"}),
        now=NOW,
    )
    assert bad_rules.sla is not None
    assert bad_rules.sla.coverage_start_hour == 9

    clamped = evaluate_mapping_record(
        _record(sla_rules={"coverage_start_hour": 30}),
        now=NOW,
    )
    assert clamped.sla is not None
    assert clamped.sla.coverage_start_hour == 23


def test_evaluate_coverage_start_hour_when_rules_none() -> None:
    result = evaluate_mapping_record(_record(sla_rules=None), now=NOW)
    assert result.sla is not None
    assert result.sla.coverage_start_hour == 9


def test_evaluate_sla_not_configured_missing_plan_type() -> None:
    result = evaluate_mapping_record(_record(plan_type=None), now=NOW)
    assert result.status is MappingStatus.SLA_NOT_CONFIGURED


def test_evaluate_no_branch_when_timezone_missing() -> None:
    result = evaluate_mapping_record(_record(branch_timezone=None), now=NOW)
    assert result.status is MappingStatus.NO_BRANCH


def test_evaluate_naive_now_datetime() -> None:
    naive_now = datetime(2026, 6, 2, 6, 0)
    result = evaluate_mapping_record(_record(), now=naive_now)
    assert result.status is MappingStatus.ACTIVE


# --- repository ---


def test_row_to_record_full_chain() -> None:
    user = User(butterpos_user_id="u1", language_pref="roman_ur", provider_contact_id="55")
    user.id = 1
    branch = Branch(
        restaurant_id=2,
        butterpos_branch_id="b1",
        name="Branch",
        timezone="Asia/Karachi",
    )
    branch.id = 10
    restaurant = Restaurant(
        butterpos_restaurant_id="r1",
        name="Rest",
        plan_type="8h",
        payment_due=False,
    )
    restaurant.id = 20
    sla = SLAConfig(
        plan_type="8h",
        coverage_hours=8,
        first_response_minutes=15,
        resolution_minutes=60,
        escalation_after_minutes=30,
    )
    record = _row_to_record(user, branch, restaurant, sla)
    assert record.butterpos_user_id == "u1"
    assert record.plan_type == "8h"
    assert record.sla_coverage_hours == 8


def test_row_to_record_partial_chain() -> None:
    user = User(butterpos_user_id="u2", language_pref="en")
    user.id = 2
    record = _row_to_record(user, None, None, None)
    assert record.branch_id is None
    assert record.plan_type is None


def test_repository_fetch_returns_none_when_missing() -> None:
    async def _run() -> None:
        session = MagicMock()
        session.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=None)))
        repo = CustomerMappingRepository(session)
        assert await repo.get_by_butterpos_user_id("missing") is None
        assert await repo.get_by_provider_contact_id("missing") is None

    asyncio.run(_run())


def test_repository_fetch_returns_record() -> None:
    async def _run() -> None:
        user = User(butterpos_user_id="u3", language_pref="en")
        user.id = 3
        branch = Branch(
            restaurant_id=1,
            butterpos_branch_id="b3",
            name="B",
            timezone="Asia/Karachi",
        )
        branch.id = 11
        restaurant = Restaurant(
            butterpos_restaurant_id="r3",
            name="R",
            plan_type="24-7",
            payment_due=False,
        )
        restaurant.id = 21
        sla = SLAConfig(
            plan_type="24-7",
            coverage_hours=24,
            first_response_minutes=10,
            resolution_minutes=120,
            escalation_after_minutes=60,
        )

        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=(user, branch, restaurant, sla)))
        )
        repo = CustomerMappingRepository(session)
        record = await repo.get_by_butterpos_user_id("u3")
        assert record is not None
        assert record.plan_type == "24-7"

    asyncio.run(_run())


# --- service ---


def test_service_unknown_user() -> None:
    async def _run() -> None:
        session = MagicMock()
        service = CustomerMappingService(session)
        with patch.object(service._repo, "get_by_butterpos_user_id", AsyncMock(return_value=None)):
            result = await service.resolve_by_user_id("ghost")
        assert result.status is MappingStatus.UNKNOWN_USER

    asyncio.run(_run())


def test_service_unknown_contact() -> None:
    async def _run() -> None:
        session = MagicMock()
        service = CustomerMappingService(session)
        with patch.object(service._repo, "get_by_provider_contact_id", AsyncMock(return_value=None)):
            result = await service.resolve_by_contact_id("ghost-contact")
        assert result.status is MappingStatus.UNKNOWN_USER
        assert result.provider_contact_id == "ghost-contact"

    asyncio.run(_run())


def test_service_resolve_active_user() -> None:
    async def _run() -> None:
        session = MagicMock()
        service = CustomerMappingService(session)
        with patch.object(
            service._repo,
            "get_by_butterpos_user_id",
            AsyncMock(return_value=_record(plan_type="24-7", sla_coverage_hours=24)),
        ):
            result = await service.resolve_by_user_id("staff-1", now=NOW)
        assert result.status is MappingStatus.ACTIVE
        assert result.max_agent_tier == 3

    asyncio.run(_run())


def test_service_resolve_restricted_logs_warning() -> None:
    async def _run() -> None:
        session = MagicMock()
        service = CustomerMappingService(session)
        with patch.object(
            service._repo,
            "get_by_butterpos_user_id",
            AsyncMock(return_value=_record(payment_due=True)),
        ):
            result = await service.resolve_by_user_id("staff-1", now=NOW)
        assert result.status is MappingStatus.PAYMENT_DUE

    asyncio.run(_run())


def test_service_resolve_by_contact_id_active() -> None:
    async def _run() -> None:
        session = MagicMock()
        service = CustomerMappingService(session)
        with patch.object(
            service._repo,
            "get_by_provider_contact_id",
            AsyncMock(return_value=_record(plan_type="16h", sla_coverage_hours=16)),
        ):
            result = await service.resolve_by_contact_id("101", now=NOW)
        assert result.status is MappingStatus.ACTIVE
        assert result.provider_contact_id == "101"

    asyncio.run(_run())


def test_service_resolve_uses_current_time_when_now_omitted() -> None:
    async def _run() -> None:
        session = MagicMock()
        service = CustomerMappingService(session)
        with patch.object(
            service._repo,
            "get_by_butterpos_user_id",
            AsyncMock(return_value=_record(plan_type="24-7", sla_coverage_hours=24)),
        ):
            result = await service.resolve_by_user_id("staff-1")
        assert result.status is MappingStatus.ACTIVE

    asyncio.run(_run())
