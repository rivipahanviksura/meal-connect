from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status, Path
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
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
    DonationCancellation,
    DonationUpdate,
    DonationDetailResponse
)
from app.services.donation_browse_service import browse_available_donations
from app.services.donation_service import create_donation
from app.services.donation_lifecycle import cancel_donation, update_donation
from app.services.donation_detail_service import get_donation_detail

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



def _validate_browse_cutoffs_before_auth(request: Request) -> None:
    """Reject invalid cutoff timestamps before DB-backed authorization runs.

    FastAPI resolves route dependencies before validating endpoint query models.
    Reuse the schema here for the two cutoffs; retain Query() on the endpoint
    for full filter validation and OpenAPI documentation.
    """
    cutoffs = {
        name: request.query_params[name]
        for name in ("available_before", "pickup_deadline_before")
        if name in request.query_params
    }
    if not cutoffs:
        return

    try:
        DonationBrowseQuery.model_validate(cutoffs)
    except ValidationError as exc:
        errors = [
            {**error, "loc": ("query", *error["loc"])}
            for error in exc.errors(include_context=False, include_url=False)
        ]
        raise RequestValidationError(errors) from exc


@router.get(
    "",
    response_model=DonationListResponse,
    dependencies=[
        Depends(_validate_browse_cutoffs_before_auth),
        Depends(require_roles(UserRole.ngo_staff)),
        Depends(get_current_organization),
    ],
)
def browse_donation_listings(
    filters: Annotated[DonationBrowseQuery, Query()],
    db: Session = Depends(get_db),
) -> DonationListResponse:
    return browse_available_donations(db, filters=filters)

DonationId = Annotated[int, Path(gt=0, le=2**63 - 1)]

@router.get(
    "/{donation_id}",
    response_model=DonationDetailResponse,
)
def get_donation_listing_detail(
    donation_id: DonationId,
    current_user: User = Depends(
        require_roles(UserRole.ngo_staff, UserRole.business_staff)
    ),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    donation = get_donation_detail(
        db=db,
        donation_id=donation_id,
        organization=organization,
        user_role=current_user.role,
    )

    return {"data": donation}

@router.patch(
    "/{donation_id}",
    response_model=DonationResponse,
    dependencies=[Depends(require_roles(UserRole.business_staff))],
)
def edit_donation(
    donation_id: DonationId,
    payload: DonationUpdate,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    return {
        "data": update_donation(db, donation_id, organization.organization_id, payload)
    }


@router.post("/{donation_id}/cancel", response_model=DonationResponse)
def cancel_donation_listing(
    donation_id: DonationId,
    current_user: User = Depends(require_roles(UserRole.business_staff)),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
    payload: DonationCancellation | None = None,
):
    return {
        "data": cancel_donation(
            db,
            donation_id,
            organization.organization_id,
            current_user.user_id,
            payload.reason if payload else None,
        )
    }
