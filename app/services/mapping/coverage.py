"""Support coverage window evaluation in branch local time — Task 1.6."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def is_within_coverage_window(
    *,
    now_utc: datetime,
    branch_timezone: str,
    coverage_hours: int,
    coverage_start_hour: int = 9,
) -> bool:
    """Return True when local branch time falls inside the daily support window."""
    if coverage_hours >= 24:
        return True
    try:
        local = now_utc.astimezone(ZoneInfo(branch_timezone))
    except ZoneInfoNotFoundError:
        return False
    end_hour = min(coverage_start_hour + coverage_hours, 24)
    return coverage_start_hour <= local.hour < end_hour
