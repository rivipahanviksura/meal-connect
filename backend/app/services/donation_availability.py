from datetime import datetime, timezone

from app.db.models.donation import Donation, DonationStatus


def as_utc(value: datetime, *, field_name: str) -> datetime:
    if value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")

    return value.astimezone(timezone.utc)


def has_pickup_deadline_passed(
    pickup_deadline: datetime,
    *,
    now: datetime | None = None,
) -> bool:
    current_time = now if now is not None else datetime.now(timezone.utc)

    deadline_utc = as_utc(
        pickup_deadline,
        field_name="pickup_deadline",
    )
    current_utc = as_utc(
        current_time,
        field_name="now",
    )

    return current_utc >= deadline_utc


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

    current_time = now if now is not None else datetime.now(timezone.utc)

    current_utc = as_utc(
        current_time,
        field_name="now",
    )
    available_from_utc = as_utc(
        donation.available_from,
        field_name="available_from",
    )
    deadline_utc = as_utc(
        donation.pickup_deadline,
        field_name="pickup_deadline",
    )

    if not available_from_utc <= current_utc < deadline_utc:
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