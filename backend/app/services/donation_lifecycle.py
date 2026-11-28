from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exception_handlers import APIException
from app.db.models.donation import Donation, DonationStatus
from app.db.models.donation_request import DonationRequest, RequestStatus
from app.db.models.pickup import Pickup
from app.db.models.status_history import StatusHistory
from app.schemas.donation import DonationCreate, DonationUpdate


EDITABLE_STATES = {DonationStatus.draft, DonationStatus.available}
ALLOCATION_SENSITIVE_FIELDS = {
    "total_quantity",
    "quantity_unit",
    "prepared_at",
    "available_from",
    "pickup_deadline",
    "pickup_address",
    "pickup_city",
}


def _lock_owned_donation(
    db: Session, donation_id: int, organization_id: int
) -> Donation:
    donation = db.scalar(
        select(Donation)
        .where(
            Donation.donation_id == donation_id,
            Donation.organization_id == organization_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if donation is None:
        raise APIException(404, "NOT_FOUND", "Donation not found.")
    return donation


def update_donation(
    db: Session,
    donation_id: int,
    organization_id: int,
    update: DonationUpdate,
) -> Donation:
    try:
        donation = _lock_owned_donation(db, donation_id, organization_id)
        if donation.status not in EDITABLE_STATES:
            raise APIException(
                409, "INVALID_STATE_TRANSITION", "This donation cannot be edited."
            )

        changes = update.model_dump(exclude_unset=True)
        if not changes:
            raise APIException(
                422, "VALIDATION_ERROR", "Provide at least one editable field."
            )

        if donation.allocated_quantity and ALLOCATION_SENSITIVE_FIELDS.intersection(changes):
            raise APIException(
                409, "QUANTITY_CONFLICT", "Allocated donation details cannot be changed."
            )

        existing = {
            field: getattr(donation, field)
            for field in DonationUpdate.model_fields
        }
        try:
            validated = DonationCreate.model_validate({**existing, **changes})
        except ValidationError as exc:
            fields = [
                {
                    "field": ".".join(map(str, error["loc"])) or "request",
                    "message": error["msg"],
                    "code": error["type"],
                }
                for error in exc.errors(include_input=False, include_context=False)
            ]
            raise APIException(
                422, "VALIDATION_ERROR", "Please correct the invalid request fields.", fields
            ) from None

        now = datetime.now(timezone.utc)
        if (
            donation.status == DonationStatus.available
            and min(donation.pickup_deadline, validated.pickup_deadline) <= now
        ):
            raise APIException(409, "DONATION_EXPIRED", "An expired donation cannot be edited.")

        for field in changes:
            setattr(donation, field, getattr(validated, field))
        donation.updated_at = now
        db.commit()
    except Exception:
        db.rollback()
        raise

    return donation


def cancel_donation(
    db: Session,
    donation_id: int,
    organization_id: int,
    user_id: int,
    reason: str | None,
) -> Donation:
    try:
        donation = _lock_owned_donation(db, donation_id, organization_id)
        if donation.status == DonationStatus.cancelled:
            db.rollback()
            return donation

        if donation.status not in EDITABLE_STATES:
            raise APIException(
                409, "INVALID_STATE_TRANSITION", "This donation cannot be cancelled."
            )

        now = datetime.now(timezone.utc)
        if donation.status == DonationStatus.available and donation.pickup_deadline <= now:
            raise APIException(
                409, "DONATION_EXPIRED", "An expired donation cannot be cancelled."
            )

        active_request = db.scalar(
            select(DonationRequest.request_id)
            .where(
                DonationRequest.donation_id == donation_id,
                DonationRequest.status.in_(
                    (RequestStatus.pending, RequestStatus.approved, RequestStatus.fulfilled)
                ),
            )
            .limit(1)
        )
        pickup = db.scalar(
            select(Pickup.pickup_id)
            .join(DonationRequest, Pickup.request_id == DonationRequest.request_id)
            .where(DonationRequest.donation_id == donation_id)
            .limit(1)
        )
        if donation.allocated_quantity or active_request is not None or pickup is not None:
            raise APIException(
                409,
                "INVALID_STATE_TRANSITION",
                "Resolve dependent requests or pickups before cancellation.",
            )

        db.add(
            StatusHistory(
                entity_type="donation",
                entity_id=donation_id,
                old_status=donation.status.value,
                new_status=DonationStatus.cancelled.value,
                changed_by_user_id=user_id,
                change_reason=reason,
            )
        )
        donation.status = DonationStatus.cancelled
        donation.updated_at = now
        db.commit()
    except Exception:
        db.rollback()
        raise

    return donation