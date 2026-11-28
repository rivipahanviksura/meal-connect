from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exception_handlers import APIException
from app.db.models.donation import Donation, DonationStatus
from app.db.models.organization import Organization
from app.db.models.user import User
from app.schemas.donation import DonationCreate


def create_donation(
    db: Session,
    donation_data: DonationCreate,
    organization: Organization,
    current_user: User,
) -> Donation:
    if donation_data.organization_id not in (None, organization.organization_id):
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="You can only create donations for your organization.",
        )

    if (
        donation_data.status == "available"
        and donation_data.pickup_deadline.astimezone(timezone.utc) <= datetime.now(timezone.utc)
    ):
        raise APIException(
            status_code=409,
            code="DONATION_EXPIRED",
            message="An available donation must have a future pickup deadline.",
        )

    donation = Donation(
        organization_id=organization.organization_id,
        created_by_user_id=current_user.user_id,
        status=DonationStatus(donation_data.status),
        title=donation_data.title,
        category=donation_data.category,
        description=donation_data.description,
        total_quantity=donation_data.total_quantity,
        quantity_unit=donation_data.quantity_unit,
        allergen_info=donation_data.allergen_info,
        storage_instructions=donation_data.storage_instructions,
        prepared_at=donation_data.prepared_at,
        available_from=donation_data.available_from,
        pickup_deadline=donation_data.pickup_deadline,
        pickup_address=donation_data.pickup_address,
        pickup_city=donation_data.pickup_city,
    )

    try:
        db.add(donation)
        db.flush()
        db.refresh(donation)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return donation
