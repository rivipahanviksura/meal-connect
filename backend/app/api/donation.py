
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_organization,
    require_roles,
)
from app.db.models.organization import Organization, OrganizationType
from app.db.models.user import User, UserRole
from app.db.models.donation import Donation
from app.db.session import get_db
from app.core.exception_handlers import APIException
from app.schemas.donation import DonationUpdate, DonationCancel
from app.services.donation import edit_donation, cancel_donation


router = APIRouter(prefix="/donations", tags=["Donations"])


class DonationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    donation_id: int
    organization_id: int
    title: str
    category: str
    description: str | None
    total_quantity: Decimal
    allocated_quantity: Decimal
    quantity_unit: str
    allergen_info: str | None
    storage_instructions: str | None
    prepared_at: datetime | None
    available_from: datetime
    pickup_deadline: datetime
    pickup_address: str
    pickup_city: str
    status: str
    created_at: datetime
    updated_at: datetime


def get_business_organization(
    organization: Organization = Depends(get_current_organization),
    current_user: User = Depends(require_roles(UserRole.business_staff)),
) -> Organization:

    if organization.type not in (
        OrganizationType.restaurant,
        OrganizationType.bakery,
    ):
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="Only approved businesses can manage donations.",
        )

    return organization


@router.patch(
    "/{donation_id}",
    response_model=DonationResponse,
    status_code=200,
)
def update_donation_endpoint(
    donation_id: int,
    data: DonationUpdate,
    organization: Organization = Depends(get_business_organization),
    db: Session = Depends(get_db),
):
    return edit_donation(
        db=db,
        donation_id=donation_id,
        organization_id=organization.organization_id,
        data=data,
    )


@router.post(
    "/{donation_id}/cancel",
    response_model=DonationResponse,
    status_code=200,
)
def cancel_donation_endpoint(
    donation_id: int,
    data: DonationCancel | None = None,
    organization: Organization = Depends(get_business_organization),
    db: Session = Depends(get_db),
):
    return cancel_donation(
        db=db,
        donation_id=donation_id,
        organization_id=organization.organization_id,
    )
