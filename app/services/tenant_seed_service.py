"""Persist validated tenant export into Postgres — Task 1.7."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.branch import Branch
from app.db.models.restaurant import Restaurant
from app.db.models.sla_config import SLAConfig
from app.db.models.user import User
from app.schemas.tenant_export import (
    ALLOWED_PLAN_TYPES,
    BranchExportRow,
    RestaurantExportRow,
    SlaConfigExportRow,
    TenantExportDocument,
    UserExportRow,
)

DEFAULT_SLA_BY_PLAN: dict[str, SlaConfigExportRow] = {
    "8h": SlaConfigExportRow(
        plan_type="8h",
        coverage_hours=8,
        first_response_minutes=30,
        resolution_minutes=240,
        escalation_after_minutes=120,
        description="8-hour support window",
        rules={"coverage_start_hour": 9},
    ),
    "16h": SlaConfigExportRow(
        plan_type="16h",
        coverage_hours=16,
        first_response_minutes=20,
        resolution_minutes=180,
        escalation_after_minutes=90,
        description="16-hour support window",
        rules={"coverage_start_hour": 8},
    ),
    "24-7": SlaConfigExportRow(
        plan_type="24-7",
        coverage_hours=24,
        first_response_minutes=15,
        resolution_minutes=120,
        escalation_after_minutes=60,
        description="24/7 support",
        rules={},
    ),
}


@dataclass(frozen=True)
class TenantSeedSummary:
    """Counts from a seed run."""

    restaurants: int
    branches: int
    users: int
    sla_configs: int
    dry_run: bool


class TenantSeedService:
    """Upsert tenant export rows into middleware Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def seed(
        self,
        document: TenantExportDocument,
        *,
        dry_run: bool = False,
        seed_default_sla: bool = False,
    ) -> TenantSeedSummary:
        sla_rows = list(document.sla_configs)
        if seed_default_sla:
            sla_rows = _merge_default_sla(sla_rows)

        if dry_run:
            return TenantSeedSummary(
                restaurants=len(document.restaurants),
                branches=len(document.branches),
                users=len(document.users),
                sla_configs=len(sla_rows),
                dry_run=True,
            )

        restaurant_map = await self._upsert_restaurants(document.restaurants)
        branch_map = await self._upsert_branches(document.branches, restaurant_map)
        await self._upsert_users(document.users, branch_map)
        await self._upsert_sla_configs(sla_rows)
        await self._session.flush()

        return TenantSeedSummary(
            restaurants=len(document.restaurants),
            branches=len(document.branches),
            users=len(document.users),
            sla_configs=len(sla_rows),
            dry_run=False,
        )

    async def _upsert_restaurants(
        self,
        rows: list[RestaurantExportRow],
    ) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for row in rows:
            existing = await self._session.scalar(
                select(Restaurant).where(
                    Restaurant.butterpos_restaurant_id == row.butterpos_restaurant_id
                )
            )
            if existing is None:
                existing = Restaurant(
                    butterpos_restaurant_id=row.butterpos_restaurant_id,
                    name=row.name,
                    plan_type=row.plan_type,
                    payment_due=row.payment_due,
                    expiry=row.expiry,
                )
                self._session.add(existing)
                await self._session.flush()
            else:
                existing.name = row.name
                existing.plan_type = row.plan_type
                existing.payment_due = row.payment_due
                existing.expiry = row.expiry
            mapping[row.butterpos_restaurant_id] = existing.id
        return mapping

    async def _upsert_branches(
        self,
        rows: list[BranchExportRow],
        restaurant_map: dict[str, int],
    ) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for row in rows:
            restaurant_id = restaurant_map[row.butterpos_restaurant_id]
            existing = await self._session.scalar(
                select(Branch).where(Branch.butterpos_branch_id == row.butterpos_branch_id)
            )
            if existing is None:
                existing = Branch(
                    restaurant_id=restaurant_id,
                    butterpos_branch_id=row.butterpos_branch_id,
                    name=row.name,
                    timezone=row.timezone,
                    devices=row.devices,
                )
                self._session.add(existing)
                await self._session.flush()
            else:
                existing.restaurant_id = restaurant_id
                existing.name = row.name
                existing.timezone = row.timezone
                existing.devices = row.devices
            mapping[row.butterpos_branch_id] = existing.id
        return mapping

    async def _upsert_users(
        self,
        rows: list[UserExportRow],
        branch_map: dict[str, int],
    ) -> None:
        for row in rows:
            branch_id = (
                branch_map[row.butterpos_branch_id]
                if row.butterpos_branch_id is not None
                else None
            )
            existing = await self._session.scalar(
                select(User).where(User.butterpos_user_id == row.butterpos_user_id)
            )
            if existing is None:
                self._session.add(
                    User(
                        butterpos_user_id=row.butterpos_user_id,
                        branch_id=branch_id,
                        provider_contact_id=row.provider_contact_id,
                        language_pref=row.language_pref,
                    )
                )
            else:
                existing.branch_id = branch_id
                existing.provider_contact_id = row.provider_contact_id
                existing.language_pref = row.language_pref

    async def _upsert_sla_configs(self, rows: list[SlaConfigExportRow]) -> None:
        for row in rows:
            existing = await self._session.scalar(
                select(SLAConfig).where(SLAConfig.plan_type == row.plan_type)
            )
            if existing is None:
                self._session.add(
                    SLAConfig(
                        plan_type=row.plan_type,
                        coverage_hours=row.coverage_hours,
                        first_response_minutes=row.first_response_minutes,
                        resolution_minutes=row.resolution_minutes,
                        escalation_after_minutes=row.escalation_after_minutes,
                        description=row.description,
                        rules=row.rules,
                        is_active=row.is_active,
                    )
                )
            else:
                existing.coverage_hours = row.coverage_hours
                existing.first_response_minutes = row.first_response_minutes
                existing.resolution_minutes = row.resolution_minutes
                existing.escalation_after_minutes = row.escalation_after_minutes
                existing.description = row.description
                existing.rules = row.rules
                existing.is_active = row.is_active


def _merge_default_sla(rows: list[SlaConfigExportRow]) -> list[SlaConfigExportRow]:
    by_plan = {row.plan_type: row for row in rows}
    for plan_type in sorted(ALLOWED_PLAN_TYPES):
        by_plan.setdefault(plan_type, DEFAULT_SLA_BY_PLAN[plan_type])
    return [by_plan[plan] for plan in sorted(by_plan)]
