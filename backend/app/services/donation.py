
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exception_handlers import APIException
from app.db.models.donation import Donation, DonationStatus
from app.db.models.donation_request import DonationRequest, RequestStatus
from app.db.models.pickup import Pickup, PickupStatus
from app.schemas.donation import DonationUpdate


def conflict(message: str):
    raise APIException(
        status_code=409,
        code="INVALID_STATE_TRANSITION",
        message=message,
    )


def get_locked_donation(
    db: Session,
    donation_id: int,
    organization_id: int,
) -> Donation:
    statement = (
        select(Donation)
        .where(
            Donation.donation_id == donation_id,
            Donation.organization_id == organization_id,
        )
        .with_for_update()
    )

    donation = db.scalar(statement)

    if donation is None:
        raise APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Donation not found.",
        )

    return donation


def has_active_requests(
    db: Session,
    donation_id: int,
) -> bool:
    statement = (
        select(DonationRequest.request_id)
        .where(
            DonationRequest.donation_id == donation_id,
            DonationRequest.status.in_(
                [
                    RequestStatus.pending,
                    RequestStatus.approved,
                    RequestStatus.fulfilled,
                ]
            ),
        )
        .limit(1)
    )

    return db.scalar(statement) is not None


def has_active_pickups(
    db: Session,
    donation_id: int,
) -> bool:
    statement = (
        select(Pickup.pickup_id)
        .join(
            DonationRequest,
            Pickup.request_id == DonationRequest.request_id,
        )
        .where(
            DonationRequest.donation_id == donation_id,
            Pickup.status != PickupStatus.cancelled,
        )
        .limit(1)
    )

    return db.scalar(statement) is not None


def edit_donation(
    db: Session,
    donation_id: int,
    organization_id: int,
    data: DonationUpdate,
) -> Donation:

    donation = get_locked_donation(
        db,
        donation_id,
        organization_id,
    )

    # Only draft or available donations can be edited.
    if donation.status not in (
        DonationStatus.draft,
        DonationStatus.available,
    ):
        conflict(
            "Donation cannot be edited in its current state."
        )

    changes = data.model_dump(exclude_unset=True)

    # Quantity and time-related fields cannot change
    # after an approved allocation.
    restricted_fields = {
        "total_quantity",
        "available_from",
        "pickup_deadline",
        "prepared_at",
    }

    if restricted_fields.intersection(changes):
        if donation.allocated_quantity > 0:
            conflict(
                "Quantity and deadlines cannot change "
                "after allocation."
            )

        approved_request = db.scalar(
            select(DonationRequest.request_id)
            .where(
                DonationRequest.donation_id == donation_id,
                DonationRequest.status.in_(
                    [
                        RequestStatus.approved,
                        RequestStatus.fulfilled,
                    ]
                ),
            )
            .limit(1)
        )

        if approved_request is not None:
            conflict(
                "Donation has approved or fulfilled requests."
            )

    # STEP 57 FIX:
    # Validate dates before modifying the donation object.
    available_from = changes.get(
        "available_from",
        donation.available_from,
    )

    pickup_deadline = changes.get(
        "pickup_deadline",
        donation.pickup_deadline,
    )

    prepared_at = changes.get(
        "prepared_at",
        donation.prepared_at,
    )

    if pickup_deadline <= available_from:
        conflict(
            "Pickup deadline must be after available time."
        )

    if (
        prepared_at is not None
        and prepared_at > pickup_deadline
    ):
        conflict(
            "Prepared time cannot be after pickup deadline."
        )

    # Apply updates only after all checks have passed.
    for field, value in changes.items():
        setattr(donation, field, value)

    donation.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(donation)

    return donation


def cancel_donation(
    db: Session,
    donation_id: int,
    organization_id: int,
) -> Donation:

    donation = get_locked_donation(
        db,
        donation_id,
        organization_id,
    )

    # Only draft or available donations may be cancelled.
    if donation.status not in (
        DonationStatus.draft,
        DonationStatus.available,
    ):
        conflict(
            "Donation cannot be cancelled in its current state."
        )

    if donation.allocated_quantity > 0:
        conflict(
            "Donation has allocated quantity."
        )

    if has_active_requests(db, donation_id):
        conflict(
            "Donation has active requests."
        )

    if has_active_pickups(db, donation_id):
        conflict(
            "Donation has an active pickup."
        )

    donation.status = DonationStatus.cancelled
    donation.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(donation)

    return donation
