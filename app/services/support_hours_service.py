"""Timezone-aware support hour enforcement."""


class SupportHoursService:
    """Determines whether support is available based on plan type and branch timezone."""

    def is_within_support_hours(self, plan_type: str, timezone: str) -> bool:
        raise NotImplementedError

    def next_available_time(self, plan_type: str, timezone: str) -> str:
        raise NotImplementedError
