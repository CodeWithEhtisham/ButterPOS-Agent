"""Load and validate ButterPOS tenant export files — Task 1.7."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas.tenant_export import (
    BranchExportRow,
    RestaurantExportRow,
    SlaConfigExportRow,
    TenantExportDocument,
    UserExportRow,
)


@dataclass(frozen=True)
class TenantExportLoadResult:
    """Outcome of parsing an export file."""

    document: TenantExportDocument
    source: Path
    format: str


class TenantExportLoadError(ValueError):
    """Export file could not be parsed or validated."""


def load_tenant_export(path: Path) -> TenantExportLoadResult:
    """Load JSON envelope or CSV directory into a validated TenantExportDocument."""
    if not path.exists():
        raise TenantExportLoadError(f"Export path not found: {path}")

    if path.is_dir():
        return _load_csv_directory(path)
    if path.suffix.lower() == ".json":
        return _load_json_file(path)
    raise TenantExportLoadError(
        f"Unsupported export path {path} — use .json file or directory of CSVs"
    )


def _load_json_file(path: Path) -> TenantExportLoadResult:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TenantExportLoadError(f"Invalid JSON in {path}: {exc}") from exc

    try:
        document = TenantExportDocument.model_validate(raw)
    except ValidationError as exc:
        raise TenantExportLoadError(f"Export validation failed: {exc}") from exc

    return TenantExportLoadResult(document=document, source=path, format="json")


def _load_csv_directory(path: Path) -> TenantExportLoadResult:
    restaurants = _read_csv_rows(path / "restaurants.csv", RestaurantExportRow)
    branches = _read_csv_rows(path / "branches.csv", BranchExportRow)
    users = _read_csv_rows(path / "users.csv", UserExportRow)
    sla_path = path / "sla_configs.csv"
    sla_configs = _read_csv_rows(sla_path, SlaConfigExportRow) if sla_path.exists() else []

    payload: dict[str, Any] = {
        "schema_version": "1",
        "restaurants": restaurants,
        "branches": branches,
        "users": users,
        "sla_configs": sla_configs,
    }
    try:
        document = TenantExportDocument.model_validate(payload)
    except ValidationError as exc:
        raise TenantExportLoadError(f"CSV export validation failed: {exc}") from exc

    return TenantExportLoadResult(document=document, source=path, format="csv")


def _read_csv_rows(path: Path, model: type[Any]) -> list[dict[str, Any]]:
    if not path.exists():
        if model is RestaurantExportRow:
            raise TenantExportLoadError(f"Missing required CSV: {path}")
        return []

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, Any]] = []
        for row in reader:
            cleaned = {key: _coerce_csv_value(key, value) for key, value in row.items() if key}
            rows.append(cleaned)
    return [model.model_validate(item).model_dump(mode="json") for item in rows]


def _coerce_csv_value(key: str, value: str | None) -> Any:
    if value is None or value == "":
        return None
    if key in {"payment_due", "is_active"}:
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if key == "devices":
        if value.strip() == "[]":
            return []
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    if key == "rules":
        if value.strip() in {"", "{}"}:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return value.strip()
