from collections.abc import Callable

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.auth import error_response
from app.db.models.organization import Organization, OrganizationVerification, VerificationStatus
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.organization_application import (
    ApplicationDraftResponse,
    ApplicationListResponse,
    ApplicationPagination,
    ApplicationRequest,
    ApplicationSummary,
)
from app.services.organization_application import (
    ApplicantNotAllowedError,
    ApplicationAlreadyExistsError,
    RegistrationNumberAlreadyExistsError,
    create_application_draft,
    get_own_application,
)

VERIFICATION_LABELS = {
    VerificationStatus.pending: "pending_verification",
    VerificationStatus.approved: "verified",
    VerificationStatus.rejected: "rejected",
    VerificationStatus.suspended: "suspended",
}


def application_summary(db: Session, organization: Organization) -> ApplicationSummary:
    status = (
        "draft" if organization.submitted_at is None
        else VERIFICATION_LABELS[organization.verification_status]
    )
    review_note = None
    if status == "rejected":
        review_note = db.scalar(
            select(OrganizationVerification.review_note)
            .where(
                OrganizationVerification.organization_id == organization.organization_id,
                OrganizationVerification.decision == VerificationStatus.rejected,
            )
            .order_by(
                OrganizationVerification.reviewed_at.desc(),
                OrganizationVerification.verification_id.desc(),
            )
            .limit(1)
        )
    return ApplicationSummary(
        application_id=organization.organization_id,
        organization_id=organization.organization_id,
        name=organization.name,
        status=status,
        review_note=review_note,
    )


def create_organization_application_router(get_current_user: Callable[..., User]) -> APIRouter:
    """Build the routes with the application's authenticated-user dependency."""
    router = APIRouter(prefix="/organization-applications", tags=["Organization Applications"])

    @router.post("", response_model=ApplicationDraftResponse, status_code=201)
    def create_draft(
        payload: ApplicationRequest,
        applicant: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        try:
            draft = create_application_draft(db, applicant.user_id, payload)
        except ApplicantNotAllowedError:
            return error_response(403, "FORBIDDEN", "This account cannot create this application.")
        except ApplicationAlreadyExistsError:
            return error_response(409, "ALREADY_EXISTS", "This account already has an application.")
        except RegistrationNumberAlreadyExistsError:
            return error_response(409, "ALREADY_EXISTS", "This registration number is already in use.")
        except SQLAlchemyError:
            return error_response(500, "INTERNAL_ERROR", "Unable to create the application.")
        return ApplicationDraftResponse(data=draft)

    @router.get("/me", response_model=ApplicationListResponse)
    def list_own_applications(
        applicant: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        try:
            organization = get_own_application(db, applicant.user_id)
            data = [] if organization is None else [application_summary(db, organization)]
        except ApplicantNotAllowedError:
            return error_response(403, "FORBIDDEN", "This account cannot view applications.")
        except SQLAlchemyError:
            return error_response(500, "INTERNAL_ERROR", "Unable to load the application.")
        total = 1 if data else 0
        return ApplicationListResponse(
            data=data,
            pagination=ApplicationPagination(total_items=total, total_pages=total),
        )

    return router
