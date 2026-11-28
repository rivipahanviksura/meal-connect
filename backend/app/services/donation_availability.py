"""Shared donation visibility and deadline guards.

Use these functions from donation discovery, NGO request creation, and business
approval services so all backend paths apply the same time boundary rules.
"""

from datetime import datetime

from app.core.timezone import to_utc, utc_now
from app.db.models.donation import Donation, DonationStatus


class DonationExpiredError(Exception):
    """The donation cannot accept requests after its pickup deadline."""

    code = "DONATION_EXPIRED"

    DEFAULT_MESSAGE = (
        "The donation is expired or its pickup deadline has passed."
    )

    def __init__(self, message: str = DEFAULT_MESSAGE) -> None:
        super().__init__(message)


def has_pickup_deadline_passed(
    pickup_deadline: datetime,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True at or after the deadline; the deadline is exclusive."""
    current_utc = to_utc(
        now if now is not None else utc_now(),
        field_name="now",
    )
    deadline_utc = to_utc(
        pickup_deadline,
        field_name="pickup_deadline",
    )
    return current_utc >= deadline_utc


def is_donation_requestable(
    donation: Donation,
    *,
    now: datetime | None = None,
) -> bool:
    """Check whether a donation may be discovered/requested at ``now``.

    Availability starts inclusively and ends exclusively:
        available_from <= now < pickup_deadline
    """
    if donation.status not in {
        DonationStatus.available,
        DonationStatus.partially_allocated,
    }:
        return False

    current_utc = to_utc(
        now if now is not None else utc_now(),
        field_name="now",
    )
    available_from_utc = to_utc(
        donation.available_from,
        field_name="available_from",
    )
    deadline_utc = to_utc(
        donation.pickup_deadline,
        field_name="pickup_deadline",
    )

    is_within_window = available_from_utc <= current_utc < deadline_utc
    has_remaining_quantity = (
        donation.allocated_quantity < donation.total_quantity
    )
    return is_within_window and has_remaining_quantity


def ensure_donation_not_expired(
    donation: Donation,
    *,
    now: datetime | None = None,
) -> None:
    """Raise the MEAL-62 DONATION_EXPIRED conflict when the deadline is due."""
    if donation.status == DonationStatus.expired or has_pickup_deadline_passed(
        donation.pickup_deadline,
        now=now,
    ):
        raise DonationExpiredError()