"""Post-seed validation — Task 1.7.2 joint sign-off checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.branch import Branch
from app.db.models.restaurant import Restaurant
from app.db.models.sla_config import SLAConfig
from app.db.models.user import User
from app.models.customer_mapping import MappingStatus
from app.services.customer_mapping_service import CustomerMappingService

# Demo fixture expectations (scripts/fixtures/sample_tenant_export.json)
DEMO_USER_EXPECTATIONS: dict[str, MappingStatus] = {
    "demo-user-active": MappingStatus.ACTIVE,
    "demo-user-unpaid": MappingStatus.PAYMENT_DUE,
    "demo-user-no-branch": MappingStatus.NO_BRANCH,
}

DEMO_CONTACT_EXPECTATIONS: dict[str, MappingStatus] = {
    "9001": MappingStatus.ACTIVE,
    "9002": MappingStatus.PAYMENT_DUE,
}


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class SeedValidationReport:
    checks: list[ValidationCheck]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


async def validate_seeded_data(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> SeedValidationReport:
    """Run automated checks after seed — mapping scenarios + row counts."""
    resolved_at = now or datetime(2026, 6, 2, 6, 0, tzinfo=UTC)
    checks: list[ValidationCheck] = []

    restaurant_count = await session.scalar(select(func.count()).select_from(Restaurant))
    branch_count = await session.scalar(select(func.count()).select_from(Branch))
    user_count = await session.scalar(select(func.count()).select_from(User))
    sla_count = await session.scalar(select(func.count()).select_from(SLAConfig))

    checks.append(
        ValidationCheck(
            name="restaurants_present",
            passed=bool(restaurant_count and restaurant_count >= 1),
            detail=f"restaurants={restaurant_count or 0}",
        )
    )
    checks.append(
        ValidationCheck(
            name="branches_present",
            passed=bool(branch_count and branch_count >= 1),
            detail=f"branches={branch_count or 0}",
        )
    )
    checks.append(
        ValidationCheck(
            name="users_present",
            passed=bool(user_count and user_count >= 1),
            detail=f"users={user_count or 0}",
        )
    )
    checks.append(
        ValidationCheck(
            name="sla_configs_present",
            passed=bool(sla_count and sla_count >= 3),
            detail=f"sla_configs={sla_count or 0} (expect >= 3 plan types)",
        )
    )

    mapper = CustomerMappingService(session)
    for user_id, expected in DEMO_USER_EXPECTATIONS.items():
        result = await mapper.resolve_by_user_id(user_id, now=resolved_at)
        checks.append(
            ValidationCheck(
                name=f"mapping_user_{user_id}",
                passed=result.status is expected,
                detail=f"expected={expected.value} got={result.status.value} tier={result.max_agent_tier}",
            )
        )

    for contact_id, expected in DEMO_CONTACT_EXPECTATIONS.items():
        result = await mapper.resolve_by_contact_id(contact_id, now=resolved_at)
        checks.append(
            ValidationCheck(
                name=f"mapping_contact_{contact_id}",
                passed=result.status is expected,
                detail=f"expected={expected.value} got={result.status.value}",
            )
        )

    unknown = await mapper.resolve_by_user_id("does-not-exist", now=resolved_at)
    checks.append(
        ValidationCheck(
            name="mapping_unknown_user",
            passed=unknown.status is MappingStatus.UNKNOWN_USER,
            detail=f"status={unknown.status.value}",
        )
    )

    return SeedValidationReport(checks=checks)
