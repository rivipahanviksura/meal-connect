"""Shared timestamp and timezone rules for the Meal Connect backend.

Meal Connect's business timezone is Asia/Colombo. API and database timestamps
must nevertheless represent timezone-aware instants; naive datetimes are never
silently assumed to be Colombo time.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
PROJECT_TIMEZONE_NAME = "Asia/Colombo"
PROJECT_TIMEZONE = ZoneInfo(PROJECT_TIMEZONE_NAME)


class TimezoneValidationError(ValueError):
    """Raised when an API/business timestamp does not identify an instant."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(
            f"{field_name} must include a timezone offset (ISO 8601)."
        )


def require_aware_datetime(value: datetime, *, field_name: str) -> datetime:
    """Return ``value`` if it identifies an instant, otherwise reject it."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise TimezoneValidationError(field_name)
    return value


def to_utc(value: datetime, *, field_name: str = "datetime") -> datetime:
    """Convert a timezone-aware datetime to UTC without changing its instant."""
    return require_aware_datetime(
        value,
        field_name=field_name,
    ).astimezone(UTC)


def to_project_timezone(
    value: datetime,
    *,
    field_name: str = "datetime",
) -> datetime:
    """Convert a timezone-aware instant to the project's business timezone."""
    return to_utc(value, field_name=field_name).astimezone(PROJECT_TIMEZONE)


def utc_now() -> datetime:
    """Return the current server time as an aware UTC datetime."""
    return datetime.now(UTC)
