
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exception_handlers import APIException
from app.db.models.donation import Donation
from app.db.models.organization import Organization
from app.db.models.user import UserRole
from app.services.donation_browse_service import (
    donation_visibility_conditions,
)


def get_donation_detail(
    db: Session,
    donation_id: int,
    organization: Organization,
    user_role: UserRole,
) -> Donation:
    """Retrieve donation details with role-specific visibility rules."""

    if user_role == UserRole.business_staff:
        # Businesses can view only donations owned by their organization.
        statement = select(Donation).where(
            Donation.donation_id == donation_id,
            Donation.organization_id == organization.organization_id,
        )

    elif user_role == UserRole.ngo_staff:
        # NGOs can view only donations eligible for discovery.
        now = datetime.now(timezone.utc)

        statement = (
            select(Donation)
            .join(
                Organization,
                Donation.organization_id == Organization.organization_id,
            )
            .where(
                Donation.donation_id == donation_id,
                *donation_visibility_conditions(now),
            )
        )

    else:
        raise APIException(
            403,
            "FORBIDDEN",
            "You do not have permission.",
        )

    donation = db.scalar(statement)

    if donation is None:
        raise APIException(
            404,
            "NOT_FOUND",
            "Donation not found.",
        )

    return donation
