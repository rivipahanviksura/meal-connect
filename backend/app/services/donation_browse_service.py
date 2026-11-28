from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.donation import Donation, DonationStatus
from app.db.models.organization import Organization, OrganizationType, VerificationStatus
from app.schemas.donation import (
    DonationBrowseQuery,
    DonationListItem,
    DonationListResponse,
    DonationPagination,
)

def donation_visibility_conditions(now: datetime):
    """Shared NGO donation visibility conditions."""
    remaining_quantity = (
        Donation.total_quantity - Donation.allocated_quantity
    )

    return [
        Donation.status.in_([
            DonationStatus.available,
            DonationStatus.partially_allocated,
        ]),
        Donation.available_from <= now,
        Donation.pickup_deadline > now,
        remaining_quantity > 0,
        Organization.verification_status == VerificationStatus.approved,
        Organization.type.in_([
            OrganizationType.restaurant,
            OrganizationType.bakery,
        ]),
    ]


def browse_available_donations(
    db: Session,
    *,
    filters: DonationBrowseQuery,
    now: datetime | None = None,
) -> DonationListResponse:
    current_time = now if now is not None else datetime.now(timezone.utc)

    if current_time.utcoffset() is None:
        raise ValueError("now must include a timezone")

    remaining_quantity = (
        Donation.total_quantity - Donation.allocated_quantity
    )

    conditions = donation_visibility_conditions(current_time)

    if filters.city is not None:
        conditions.append(
            func.lower(Donation.pickup_city) == filters.city.lower()
        )

    if filters.category is not None:
        conditions.append(
            func.lower(Donation.category) == filters.category.lower()
        )

    if filters.status is not None:
        conditions.append(
            Donation.status == DonationStatus(filters.status)
        )

    if filters.min_quantity is not None:
        conditions.append(
            remaining_quantity >= filters.min_quantity
        )

    if filters.available_before is not None:
        conditions.append(
            Donation.available_from <= filters.available_before
        )

    total_items = db.scalar(
        select(func.count())
        .select_from(Donation)
        .join(Organization, Donation.organization_id == Organization.organization_id)
        .where(*conditions)
    ) or 0

    sort_columns = {
        "pickup_deadline": Donation.pickup_deadline.asc(),
        "-pickup_deadline": Donation.pickup_deadline.desc(),
        "created_at": Donation.created_at.asc(),
        "-created_at": Donation.created_at.desc(),
    }

    offset = (filters.page - 1) * filters.page_size
    statement = (
        select(Donation)
        .join(Organization, Donation.organization_id == Organization.organization_id)
        .where(*conditions)
        .order_by(
            sort_columns[filters.sort],
            Donation.donation_id.asc(),
        )
        .offset(offset)
        .limit(filters.page_size)
    )

    items = (
        [DonationListItem.model_validate(donation) for donation in db.scalars(statement)]
        if offset < total_items else []
    )

    return DonationListResponse(
        data=items,
        pagination=DonationPagination(
            page=filters.page,
            page_size=filters.page_size,
            total_items=total_items,
            total_pages=(
                total_items + filters.page_size - 1
            ) // filters.page_size,
        ),
    )
