"""Donation edit/cancel routes; included alongside existing creation/browse router."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_organization, require_roles
from app.core.exception_handlers import APIException
from app.db.models.organization import Organization, OrganizationType
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.donation import DonationResponse
from app.schemas.donation_edit_cancel import DonationCancel, DonationUpdate
from app.services.donation_edit_cancel_service import edit_donation, cancel_donation

router = APIRouter(prefix="/donations", tags=["Donations"])


def get_business_organization(
    organization: Organization = Depends(get_current_organization),
    current_user: User = Depends(require_roles(UserRole.business_staff)),
) -> Organization:
    if organization.type not in (OrganizationType.restaurant, OrganizationType.bakery):
        raise APIException(status_code=403, code="FORBIDDEN",
                           message="Only approved businesses can manage donations.")
    return organization


@router.patch("/{donation_id}", response_model=DonationResponse)
def update_donation_endpoint(
    donation_id: int,
    data: DonationUpdate,
    organization: Organization = Depends(get_business_organization),
    db: Session = Depends(get_db),
):
    donation = edit_donation(db, donation_id, organization.organization_id, data)
    return {"data": donation}


@router.post("/{donation_id}/cancel", response_model=DonationResponse)
def cancel_donation_endpoint(
    donation_id: int,
    data: DonationCancel | None = None,
    organization: Organization = Depends(get_business_organization),
    current_user: User = Depends(require_roles(UserRole.business_staff)),
    db: Session = Depends(get_db),
):
    donation = cancel_donation(
        db, donation_id, organization.organization_id,
        changed_by_user_id=current_user.user_id,
        reason=data.reason if data else None,
    )
    return {"data": donation}
