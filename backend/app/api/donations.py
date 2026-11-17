from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_organization,
    require_roles,
)
from app.db.models.organization import Organization
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.donation import (
    DonationBrowseQuery,
    DonationCreate,
    DonationListResponse,
    DonationResponse,
)
from app.services.donation_browse_service import browse_available_donations
from app.services.donation_service import create_donation


router = APIRouter(prefix="/donations", tags=["Donations"])


@router.post(
    "",
    response_model=DonationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_donation_listing(
    donation_data: DonationCreate,
    current_user: User = Depends(require_roles(UserRole.business_staff)),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    donation = create_donation(
        db=db,
        donation_data=donation_data,
        organization=organization,
        current_user=current_user,
    )

    return {"data": donation}



@router.get(
    "",
    response_model=DonationListResponse,
    dependencies=[
        Depends(require_roles(UserRole.ngo_staff)),
        Depends(get_current_organization),
    ],
)
def browse_donation_listings(
    filters: Annotated[DonationBrowseQuery, Query()],
    db: Session = Depends(get_db),
) -> DonationListResponse:
    return browse_available_donations(db, filters=filters)
