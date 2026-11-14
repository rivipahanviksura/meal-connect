from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.donation import Donation, DonationStatus
from app.db.models.organization import (
    MemberStatus,
    Organization,
    OrganizationMembership,
    OrganizationType,
    VerificationStatus,
)
from app.db.models.user import AccountStatus, User, UserRole
from app.schemas.donation import (
    DonationBrowseQuery,
    DonationListItem,
    DonationListResponse,
    DonationPagination,
)


class DonationBrowseForbiddenError(Exception):
    code = "FORBIDDEN"


def ensure_verified_ngo_access(
    db: Session,
    *,
    authenticated_user_id: int,
) -> None:
    """
    The user ID must come from trusted backend authentication,
    never directly from a request parameter or client header.
    """
    statement = (
        select(OrganizationMembership.membership_id)
        .join(
            User,
            User.user_id == OrganizationMembership.user_id,
        )
        .join(
            Organization,
            Organization.organization_id
            == OrganizationMembership.organization_id,
        )
        .where(
            User.user_id == authenticated_user_id,
            User.account_status == AccountStatus.active,
            User.role == UserRole.ngo_staff,
            OrganizationMembership.member_status == MemberStatus.active,
            Organization.type == OrganizationType.ngo,
            Organization.verification_status
            == VerificationStatus.approved,
        )
        .limit(1)
    )

    membership_id = db.scalar(statement)

    if membership_id is None:
        raise DonationBrowseForbiddenError(
            "An active account with approved NGO membership is required."
        )


def browse_available_donations(
    db: Session,
    *,
    authenticated_user_id: int,
    filters: DonationBrowseQuery,
    now: datetime | None = None,
) -> DonationListResponse:
    ensure_verified_ngo_access(
        db,
        authenticated_user_id=authenticated_user_id,
    )

    current_time = now if now is not None else datetime.now(timezone.utc)

    if current_time.utcoffset() is None:
        raise ValueError("now must include a timezone")

    remaining_quantity = (
        Donation.total_quantity - Donation.allocated_quantity
    )

    conditions = [
        Donation.status.in_(
            [
                DonationStatus.available,
                DonationStatus.partially_allocated,
            ]
        ),
        Donation.available_from <= current_time,
        Donation.pickup_deadline > current_time,
        remaining_quantity > 0,
    ]

    if filters.city is not None:
        conditions.append(
            func.lower(Donation.pickup_city)
            == filters.city.strip().lower()
        )

    if filters.category is not None:
        conditions.append(
            func.lower(Donation.category)
            == filters.category.strip().lower()
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
        .where(*conditions)
    ) or 0

    sort_columns = {
        "pickup_deadline": Donation.pickup_deadline.asc(),
        "-pickup_deadline": Donation.pickup_deadline.desc(),
        "created_at": Donation.created_at.asc(),
        "-created_at": Donation.created_at.desc(),
    }

    statement = (
        select(Donation)
        .where(*conditions)
        .order_by(
            sort_columns[filters.sort],
            Donation.donation_id.asc(),
        )
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    )

    donations = db.scalars(statement).all()

    items = [
        DonationListItem(
            donation_id=donation.donation_id,
            organization_id=donation.organization_id,
            title=donation.title,
            category=donation.category,
            description=donation.description,
            total_quantity=donation.total_quantity,
            allocated_quantity=donation.allocated_quantity,
            remaining_quantity=(
                donation.total_quantity
                - donation.allocated_quantity
            ),
            quantity_unit=donation.quantity_unit,
            available_from=donation.available_from,
            pickup_deadline=donation.pickup_deadline,
            pickup_city=donation.pickup_city,
            status=donation.status.value,
        )
        for donation in donations
    ]

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