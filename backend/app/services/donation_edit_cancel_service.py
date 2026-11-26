"""Safely edit or cancel a business-owned donation in one database transaction."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exception_handlers import APIException
from app.db.models.donation import Donation, DonationStatus
from app.db.models.donation_request import DonationRequest, RequestStatus
from app.db.models.pickup import Pickup, PickupStatus
from app.db.models.status_history import StatusHistory
from app.schemas.donation_edit_cancel import DonationUpdate


ACTIVE_REQUESTS = (RequestStatus.pending, RequestStatus.approved, RequestStatus.fulfilled)
RESTRICTED_WHEN_ALLOCATED = frozenset({
    "total_quantity", "available_from", "pickup_deadline", "prepared_at",
    "quantity_unit", "pickup_address", "pickup_city",
})
RESTRICTED_WHEN_REQUESTED = frozenset({
    "total_quantity", "available_from", "pickup_deadline", "prepared_at",
    "quantity_unit", "pickup_address", "pickup_city",
})


def fail(message: str, *, code: str = "INVALID_STATE_TRANSITION") -> None:
    raise APIException(status_code=409, code=code, message=message)


def get_locked_donation(db: Session, donation_id: int, organization_id: int) -> Donation:
    donation = db.scalar(
        select(Donation)
        .where(Donation.donation_id == donation_id,
               Donation.organization_id == organization_id)
        .with_for_update()
    )
    if donation is None:
        raise APIException(status_code=404, code="NOT_FOUND", message="Donation not found.")
    return donation


def has_active_requests(db: Session, donation_id: int) -> bool:
    return db.scalar(
        select(DonationRequest.request_id)
        .where(DonationRequest.donation_id == donation_id,
               DonationRequest.status.in_(ACTIVE_REQUESTS))
        .limit(1)
    ) is not None


def has_active_pickups(db: Session, donation_id: int) -> bool:
    return db.scalar(
        select(Pickup.pickup_id)
        .join(DonationRequest, Pickup.request_id == DonationRequest.request_id)
        .where(DonationRequest.donation_id == donation_id,
               Pickup.status != PickupStatus.cancelled)
        .limit(1)
    ) is not None


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise APIException(
            status_code=409, code="INVALID_STATE_TRANSITION",
            message="Stored donation timestamp has no timezone.",
        )
    return value.astimezone(timezone.utc)


def edit_donation(db: Session, donation_id: int, organization_id: int,
                  data: DonationUpdate) -> Donation:
    try:
        donation = get_locked_donation(db, donation_id, organization_id)
        if donation.status not in (DonationStatus.draft, DonationStatus.available):
            fail("Donation cannot be edited in its current state.")

        changes = data.model_dump(exclude_unset=True)
        restricted = RESTRICTED_WHEN_ALLOCATED.intersection(changes)
        if restricted and donation.allocated_quantity > 0:
            fail("Pickup details, quantity and dates cannot change after allocation.")

        if RESTRICTED_WHEN_REQUESTED.intersection(changes) and has_active_requests(db, donation_id):
            fail("Pickup details, quantity and dates cannot change while requests exist.")

        if RESTRICTED_WHEN_REQUESTED.intersection(changes) and has_active_pickups(db, donation_id):
            fail("Pickup details, quantity and dates cannot change while pickups exist.")

        start = changes.get("available_from", donation.available_from)
        deadline = changes.get("pickup_deadline", donation.pickup_deadline)
        prepared = changes.get("prepared_at", donation.prepared_at)
        start_utc, deadline_utc = aware_utc(start), aware_utc(deadline)

        if deadline_utc <= start_utc:
            fail("Pickup deadline must be after available time.")
        if prepared is not None and aware_utc(prepared) > deadline_utc:
            fail("Prepared time cannot be after pickup deadline.")
        if donation.status == DonationStatus.available and deadline_utc <= datetime.now(timezone.utc):
            fail("An available donation must have a future pickup deadline.",
                 code="DONATION_EXPIRED")

        for name, value in changes.items():
            setattr(donation, name, value)
        donation.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(donation)
        return donation
    except Exception:
        db.rollback()
        raise


def cancel_donation(db: Session, donation_id: int, organization_id: int,
                    changed_by_user_id: int, reason: str | None = None) -> Donation:
    try:
        donation = get_locked_donation(db, donation_id, organization_id)
        if donation.status not in (DonationStatus.draft, DonationStatus.available):
            fail("Donation cannot be cancelled in its current state.")
        if donation.allocated_quantity > 0:
            fail("Donation has allocated quantity.")
        if has_active_requests(db, donation_id):
            fail("Donation has active requests.")
        if has_active_pickups(db, donation_id):
            fail("Donation has an active pickup.")

        old_status = donation.status.value
        donation.status = DonationStatus.cancelled
        donation.updated_at = datetime.now(timezone.utc)
        db.add(StatusHistory(
            entity_type="donation",
            entity_id=donation.donation_id,
            old_status=old_status,
            new_status=DonationStatus.cancelled.value,
            changed_by_user_id=changed_by_user_id,
            change_reason=reason,
        ))
        db.commit()
        db.refresh(donation)
        return donation
    except Exception:
        db.rollback()
        raise
