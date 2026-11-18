
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_ngo_donation_request,
    get_current_restaurant_donation_request,
)
from app.core.exception_handlers import APIException
from app.db.session import get_db

from app.db.models.donation_request import (
    DonationRequest,
    RequestStatus,
)
from app.db.models.pickup import Pickup, PickupStatus


def get_approved_restaurant_pickup_request(
    donation_request: DonationRequest = Depends(
        get_current_restaurant_donation_request
    ),
) -> DonationRequest:
    # MEAL-81 already checks restaurant role,
    # active membership, approval and ownership.

    if donation_request.status != RequestStatus.approved:
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="Pickup requires an approved donation request.",
        )

    return donation_request


def get_collected_ngo_request(
    donation_request: DonationRequest = Depends(
        get_current_ngo_donation_request
    ),
    db: Session = Depends(get_db),
) -> DonationRequest:
    # MEAL-81 already verifies NGO ownership.

    statement = select(Pickup).where(
        Pickup.request_id == donation_request.request_id
    )

    pickup = db.scalar(statement)

    if pickup is None:
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="Food collection is not confirmed.",
        )

    if pickup.status not in {
        PickupStatus.picked_up,
        PickupStatus.delivered,
    }:
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="Food must be collected before distribution.",
        )

    if (
        pickup.pin_verified_at is None
        or pickup.handover_confirmed_at is None
    ):
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="Pickup handover has not been verified.",
        )

    return donation_request
