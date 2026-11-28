from datetime import datetime, timedelta, timezone

import pytest

from app.core.timezone import (
    PROJECT_TIMEZONE,
    PROJECT_TIMEZONE_NAME,
    require_aware_datetime,
    to_project_timezone,
    to_utc,
)


def test_project_timezone_is_sri_lanka():
    assert PROJECT_TIMEZONE_NAME == "Asia/Colombo"
    assert datetime(2026, 11, 14, 12, 0, tzinfo=PROJECT_TIMEZONE).utcoffset() == (
        timedelta(hours=5, minutes=30)
    )


def test_colombo_local_timestamp_converts_to_utc():
    local_value = datetime(
        2026, 11, 15, 18, 0,
        tzinfo=PROJECT_TIMEZONE,
    )

    assert to_utc(local_value) == datetime(
        2026, 11, 15, 12, 30,
        tzinfo=timezone.utc,
    )


def test_utc_and_colombo_values_represent_same_instant():
    colombo_value = datetime(
        2026, 11, 15, 18, 0,
        tzinfo=PROJECT_TIMEZONE,
    )
    utc_value = datetime(
        2026, 11, 15, 12, 30,
        tzinfo=timezone.utc,
    )

    assert to_utc(colombo_value) == to_utc(utc_value)


def test_to_project_timezone_converts_an_instant_for_display():
    utc_value = datetime(
        2026, 11, 15, 12, 30,
        tzinfo=timezone.utc,
    )

    assert to_project_timezone(utc_value) == datetime(
        2026, 11, 15, 18, 0,
        tzinfo=PROJECT_TIMEZONE,
    )


@pytest.mark.parametrize("value", [
    datetime(2026, 11, 15, 18, 0),
    datetime(2026, 11, 15, 18, 0, tzinfo=None),
])
def test_naive_datetime_is_rejected(value):
    with pytest.raises(ValueError, match="timezone offset"):
        require_aware_datetime(value, field_name="pickup_deadline")


def test_naive_datetime_error_names_the_field():
    with pytest.raises(ValueError, match="available_from"):
        to_utc(datetime(2026, 11, 15, 10, 0), field_name="available_from")
