from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_organization,
    require_roles,
)
from app.db.models.organization import Organization
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.donation import (
    DonationBrowseResponse,
    DonationCreate,
)
from app.services.donation_service import (
    browse_available_donations,
    create_donation,
)


router = APIRouter(prefix="/donations", tags=["Donations"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_donation_listing(
    donation_data: DonationCreate,
    current_user: User = Depends(require_roles(UserRole.business_staff)),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    return create_donation(
        db=db,
        donation_data=donation_data,
        organization=organization,
        current_user=current_user,
    )


@router.get(
    "/",
    response_model=list[DonationBrowseResponse],
)
def browse_donation_listings(
    current_user: User = Depends(require_roles(UserRole.ngo_staff)),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    return browse_available_donations(db=db)
