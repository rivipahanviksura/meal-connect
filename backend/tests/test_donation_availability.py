from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.db.models.donation import Donation, DonationStatus
from app.services.donation_availability import (
    DonationExpiredError,
    ensure_donation_not_expired,
    has_pickup_deadline_passed,
    is_donation_requestable,
)


NOW = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)


def make_donation(**changes):
    values = {
        "status": DonationStatus.available,
        "available_from": NOW - timedelta(hours=1),
        "pickup_deadline": NOW + timedelta(hours=1),
        "total_quantity": Decimal("10.00"),
        "allocated_quantity": Decimal("0.00"),
    }
    values.update(changes)
    return Donation(**values)


@pytest.mark.parametrize(
    "offset_seconds, expected",
    [
        (1, False),
        (0, True),
        (-1, True),
    ],
)
def test_deadline_boundary(offset_seconds, expected):
    deadline = NOW + timedelta(seconds=offset_seconds)

    assert has_pickup_deadline_passed(deadline, now=NOW) is expected


def test_available_donation_before_deadline_is_requestable():
    donation = make_donation()

    assert is_donation_requestable(donation, now=NOW) is True


@pytest.mark.parametrize("offset_seconds", [0, -1])
def test_donation_at_or_after_deadline_is_not_requestable(offset_seconds):
    donation = make_donation(
        pickup_deadline=NOW + timedelta(seconds=offset_seconds)
    )

    assert is_donation_requestable(donation, now=NOW) is False


@pytest.mark.parametrize(
    "status",
    [
        DonationStatus.draft,
        DonationStatus.fully_allocated,
        DonationStatus.collected,
        DonationStatus.expired,
        DonationStatus.cancelled,
    ],
)
def test_unavailable_status_is_not_requestable(status):
    donation = make_donation(status=status)

    assert is_donation_requestable(donation, now=NOW) is False


def test_no_remaining_quantity_is_not_requestable():
    donation = make_donation(
        allocated_quantity=Decimal("10.00")
    )

    assert is_donation_requestable(donation, now=NOW) is False


def test_same_deadline_in_sri_lanka_timezone():
    sri_lanka_timezone = timezone(
        timedelta(hours=5, minutes=30)
    )
    deadline = NOW.astimezone(sri_lanka_timezone)

    assert has_pickup_deadline_passed(deadline, now=NOW) is True


def test_deadline_without_timezone_is_rejected():
    with pytest.raises(ValueError, match="pickup_deadline"):
        has_pickup_deadline_passed(
            NOW.replace(tzinfo=None),
            now=NOW,
        )


def test_current_time_without_timezone_is_rejected():
    with pytest.raises(ValueError, match="now"):
        has_pickup_deadline_passed(
            NOW,
            now=NOW.replace(tzinfo=None),
        )


def test_partially_allocated_with_stock_is_requestable():
    donation = make_donation(
        status=DonationStatus.partially_allocated,
        allocated_quantity=Decimal("4.00"),
    )

    assert is_donation_requestable(donation, now=NOW) is True


def test_partially_allocated_after_deadline_is_not_requestable():
    donation = make_donation(
        status=DonationStatus.partially_allocated,
        pickup_deadline=NOW - timedelta(seconds=1),
        allocated_quantity=Decimal("4.00"),
    )

    assert is_donation_requestable(donation, now=NOW) is False


def test_expiry_guard_allows_before_deadline():
    donation = make_donation()

    assert ensure_donation_not_expired(donation, now=NOW) is None


@pytest.mark.parametrize("offset_seconds", [0, -1])
def test_expiry_guard_rejects_at_or_after_deadline(offset_seconds):
    donation = make_donation(
        pickup_deadline=NOW + timedelta(seconds=offset_seconds)
    )

    with pytest.raises(DonationExpiredError) as error:
        ensure_donation_not_expired(donation, now=NOW)

    assert error.value.code == "DONATION_EXPIRED"


def test_expiry_guard_rejects_expired_status_with_future_deadline():
    donation = make_donation(status=DonationStatus.expired)

    with pytest.raises(DonationExpiredError):
        ensure_donation_not_expired(donation, now=NOW)


# Review fix: respect the availability start time.
def test_donation_is_not_requestable_just_before_available_from():
    donation = make_donation(available_from=NOW)

    assert is_donation_requestable(
        donation,
        now=NOW - timedelta(microseconds=1),
    ) is False


def test_donation_is_requestable_exactly_at_available_from():
    donation = make_donation(available_from=NOW)

    assert is_donation_requestable(donation, now=NOW) is True


def test_available_from_without_timezone_is_rejected():
    donation = make_donation(
        available_from=NOW.replace(tzinfo=None)
    )

    with pytest.raises(ValueError, match="available_from"):
        is_donation_requestable(donation, now=NOW)


# Review fix: the repeated DST hour represents different UTC instants.
def repeated_hour_times():
    new_york = ZoneInfo("America/New_York")

    earlier = datetime(
        2026, 11, 1, 1, 30,
        tzinfo=new_york,
        fold=0,
    )
    later = datetime(
        2026, 11, 1, 1, 30,
        tzinfo=new_york,
        fold=1,
    )

    return earlier, later


def test_dst_earlier_occurrence_is_before_deadline():
    earlier, deadline = repeated_hour_times()

    assert has_pickup_deadline_passed(
        deadline,
        now=earlier,
    ) is False


def test_dst_later_occurrence_is_at_deadline():
    _, deadline = repeated_hour_times()

    assert has_pickup_deadline_passed(
        deadline,
        now=deadline,
    ) is True


def test_requestability_during_repeated_dst_hour():
    earlier, deadline = repeated_hour_times()

    donation = make_donation(
        available_from=datetime(
            2026, 11, 1, 5, 0,
            tzinfo=timezone.utc,
        ),
        pickup_deadline=deadline,
    )

    assert is_donation_requestable(donation, now=earlier) is True
    assert is_donation_requestable(donation, now=deadline) is False


def test_available_from_during_repeated_dst_hour():
    earlier, later = repeated_hour_times()

    donation = make_donation(
        available_from=later,
        pickup_deadline=later.astimezone(timezone.utc)
        + timedelta(hours=1),
    )

    assert is_donation_requestable(donation, now=earlier) is False
    assert is_donation_requestable(donation, now=later) is True