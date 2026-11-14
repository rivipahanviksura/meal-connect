from datetime import datetime, timezone

from app.db.models.donation import Donation, DonationStatus


def has_pickup_deadline_passed(
    pickup_deadline: datetime,
    *,
    now: datetime | None = None,
) -> bool:
    current_time = now if now is not None else datetime.now(timezone.utc)

    if pickup_deadline.utcoffset() is None:
        raise ValueError("pickup_deadline must include a timezone")

    if current_time.utcoffset() is None:
        raise ValueError("now must include a timezone")

    return current_time >= pickup_deadline


def is_donation_requestable(
    donation: Donation,
    *,
    now: datetime | None = None,
) -> bool:
    if donation.status not in {
        DonationStatus.available,
        DonationStatus.partially_allocated,
    }:
        return False

    if has_pickup_deadline_passed(donation.pickup_deadline, now=now):
        return False

    return donation.allocated_quantity < donation.total_quantity


class DonationExpiredError(Exception):
    """The donation cannot accept requests after its deadline."""

    code = "DONATION_EXPIRED"


def ensure_donation_not_expired(
    donation: Donation,
    *,
    now: datetime | None = None,
) -> None:
    if (
        donation.status == DonationStatus.expired
        or has_pickup_deadline_passed(
            donation.pickup_deadline,
            now=now,
        )
    ):
        raise DonationExpiredError(
            "The donation is expired or its pickup deadline has passed."
        )