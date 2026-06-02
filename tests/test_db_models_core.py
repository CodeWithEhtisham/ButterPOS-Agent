"""Restaurant / Branch / User ORM tests — Task 1.2 sub-step 2."""

from __future__ import annotations

from app.db.base import Base
from app.db.models import Branch, Restaurant, User
from sqlalchemy.dialects.postgresql import JSONB


def test_restaurant_table_columns() -> None:
    columns = Restaurant.__table__.columns
    assert columns["butterpos_restaurant_id"].unique
    assert columns["plan_type"].nullable is False
    assert columns["payment_due"].nullable is False
    assert columns["expiry"].nullable is True


def test_branch_table_columns_and_fk() -> None:
    columns = Branch.__table__.columns
    assert columns["restaurant_id"].foreign_keys
    assert isinstance(columns["devices"].type, JSONB)
    assert columns["timezone"].nullable is False


def test_user_table_columns() -> None:
    columns = User.__table__.columns
    assert columns["butterpos_user_id"].unique
    assert columns["provider_contact_id"].unique
    assert columns["branch_id"].nullable is True
    assert columns["language_pref"].nullable is False


def test_relationships_registered() -> None:
    assert Restaurant.branches.property.mapper.class_ is Branch
    assert Branch.restaurant.property.mapper.class_ is Restaurant
    assert Branch.users.property.mapper.class_ is User
    assert User.branch.property.mapper.class_ is Branch


def test_all_models_in_metadata() -> None:
    names = {t.name for t in Base.metadata.sorted_tables}
    assert {"restaurants", "branches", "users"}.issubset(names)
