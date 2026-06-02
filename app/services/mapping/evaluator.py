"""Map DB row to CustomerMappingResult — pure logic for Task 1.6."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.customer_mapping import CustomerMappingResult, MappingStatus, SlaSnapshot
from app.repositories.customer_mapping_repository import MappingRecord
from app.services.mapping.coverage import is_within_coverage_window
from app.services.mapping.plan_status import is_plan_expired

_STATUS_MESSAGES: dict[MappingStatus, str] = {
    MappingStatus.ACTIVE: "Account active within support coverage.",
    MappingStatus.UNKNOWN_USER: "User not found — escalate to human agent.",
    MappingStatus.NO_BRANCH: "User has no branch assignment — escalate to human agent.",
    MappingStatus.PAYMENT_DUE: "Outstanding payment — Tier 1 read-only; direct user to billing.",
    MappingStatus.PLAN_EXPIRED: "Support plan expired — Tier 1 read-only; direct user to renew.",
    MappingStatus.OUTSIDE_COVERAGE: "Outside support coverage hours for this plan.",
    MappingStatus.SLA_NOT_CONFIGURED: "SLA not configured for plan — escalate to human agent.",
}

_TIER_BY_STATUS: dict[MappingStatus, int] = {
    MappingStatus.ACTIVE: 3,
    MappingStatus.UNKNOWN_USER: 1,
    MappingStatus.NO_BRANCH: 1,
    MappingStatus.PAYMENT_DUE: 1,
    MappingStatus.PLAN_EXPIRED: 1,
    MappingStatus.OUTSIDE_COVERAGE: 1,
    MappingStatus.SLA_NOT_CONFIGURED: 1,
}


def unknown_user_result(butterpos_user_id: str) -> CustomerMappingResult:
    """Build result when no user row exists."""
    return CustomerMappingResult(
        status=MappingStatus.UNKNOWN_USER,
        status_message=_STATUS_MESSAGES[MappingStatus.UNKNOWN_USER],
        max_agent_tier=_TIER_BY_STATUS[MappingStatus.UNKNOWN_USER],
        butterpos_user_id=butterpos_user_id,
    )


def unknown_contact_result(provider_contact_id: str) -> CustomerMappingResult:
    """Build result when lookup by ticketing contact id fails."""
    return CustomerMappingResult(
        status=MappingStatus.UNKNOWN_USER,
        status_message=_STATUS_MESSAGES[MappingStatus.UNKNOWN_USER],
        max_agent_tier=_TIER_BY_STATUS[MappingStatus.UNKNOWN_USER],
        provider_contact_id=provider_contact_id,
    )


def _coverage_start_hour(rules: dict[str, Any] | None) -> int:
    if not rules:
        return 9
    raw = rules.get("coverage_start_hour", 9)
    try:
        hour = int(raw)
    except (TypeError, ValueError):
        return 9
    return max(0, min(hour, 23))


def evaluate_mapping_record(record: MappingRecord, *, now: datetime) -> CustomerMappingResult:
    """Evaluate plan, payment, and coverage state from a joined DB row."""
    base = CustomerMappingResult(
        status=MappingStatus.ACTIVE,
        status_message=_STATUS_MESSAGES[MappingStatus.ACTIVE],
        max_agent_tier=_TIER_BY_STATUS[MappingStatus.ACTIVE],
        butterpos_user_id=record.butterpos_user_id,
        user_id=record.user_id,
        language_pref=record.language_pref,
        provider_contact_id=record.provider_contact_id,
        branch_id=record.branch_id,
        butterpos_branch_id=record.butterpos_branch_id,
        branch_name=record.branch_name,
        branch_timezone=record.branch_timezone,
        restaurant_id=record.restaurant_id,
        butterpos_restaurant_id=record.butterpos_restaurant_id,
        restaurant_name=record.restaurant_name,
        plan_type=record.plan_type,
        payment_due=record.payment_due,
        plan_expiry=record.plan_expiry,
    )

    if record.branch_id is None or record.branch_timezone is None:
        return base.model_copy(
            update={
                "status": MappingStatus.NO_BRANCH,
                "status_message": _STATUS_MESSAGES[MappingStatus.NO_BRANCH],
                "max_agent_tier": _TIER_BY_STATUS[MappingStatus.NO_BRANCH],
            }
        )

    if is_plan_expired(record.plan_expiry, now=now):
        return base.model_copy(
            update={
                "status": MappingStatus.PLAN_EXPIRED,
                "status_message": _STATUS_MESSAGES[MappingStatus.PLAN_EXPIRED],
                "max_agent_tier": _TIER_BY_STATUS[MappingStatus.PLAN_EXPIRED],
            }
        )

    if record.payment_due:
        return base.model_copy(
            update={
                "status": MappingStatus.PAYMENT_DUE,
                "status_message": _STATUS_MESSAGES[MappingStatus.PAYMENT_DUE],
                "max_agent_tier": _TIER_BY_STATUS[MappingStatus.PAYMENT_DUE],
            }
        )

    if record.sla_coverage_hours is None or record.plan_type is None:
        return base.model_copy(
            update={
                "status": MappingStatus.SLA_NOT_CONFIGURED,
                "status_message": _STATUS_MESSAGES[MappingStatus.SLA_NOT_CONFIGURED],
                "max_agent_tier": _TIER_BY_STATUS[MappingStatus.SLA_NOT_CONFIGURED],
            }
        )

    if record.sla_is_active is False:
        return base.model_copy(
            update={
                "status": MappingStatus.SLA_NOT_CONFIGURED,
                "status_message": _STATUS_MESSAGES[MappingStatus.SLA_NOT_CONFIGURED],
                "max_agent_tier": _TIER_BY_STATUS[MappingStatus.SLA_NOT_CONFIGURED],
            }
        )

    start_hour = _coverage_start_hour(record.sla_rules)
    within = is_within_coverage_window(
        now_utc=now if now.tzinfo else now.replace(tzinfo=UTC),
        branch_timezone=record.branch_timezone,
        coverage_hours=record.sla_coverage_hours,
        coverage_start_hour=start_hour,
    )
    sla = SlaSnapshot(
        plan_type=record.plan_type,
        coverage_hours=record.sla_coverage_hours,
        first_response_minutes=record.sla_first_response_minutes or 0,
        resolution_minutes=record.sla_resolution_minutes or 0,
        escalation_after_minutes=record.sla_escalation_after_minutes or 0,
        coverage_start_hour=start_hour,
        within_coverage=within,
    )

    if not within:
        return base.model_copy(
            update={
                "status": MappingStatus.OUTSIDE_COVERAGE,
                "status_message": _STATUS_MESSAGES[MappingStatus.OUTSIDE_COVERAGE],
                "max_agent_tier": _TIER_BY_STATUS[MappingStatus.OUTSIDE_COVERAGE],
                "sla": sla,
            }
        )

    return base.model_copy(update={"sla": sla})
