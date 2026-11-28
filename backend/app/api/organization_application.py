from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path as PathParam, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.auth import error_response
from app.db.models.organization import Organization, OrganizationVerification, VerificationStatus
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.organization_application import (
    ApplicationDocumentResponse,
    ApplicationSubmittedResponse,
    DocumentType,
    ApplicationDraftResponse,
    ApplicationListResponse,
    ApplicationPagination,
    ApplicationRequest,
    ApplicationSummary,
)
from app.services.application_submission import (
    MAX_DOCUMENT_BYTES,
    ApplicationEvidenceError,
    ApplicationNotFoundError,
    ApplicationStateError,
    save_application_document,
    submit_application,
)
from app.services.organization_application import (
    ApplicantNotAllowedError,
    ApplicationAlreadyExistsError,
    RegistrationNumberAlreadyExistsError,
    create_application_draft,
    get_application_details,
    get_own_application,
)

ApplicationId = Annotated[int, PathParam(gt=0, le=2**63 - 1)]

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
    draft_details = None
    if status == "draft":
        draft_details = get_application_details(organization)

        if organization.type.value == "ngo":
            draft_details["organization_type"] = "ngo"
        else:
            draft_details["organization_type"] = "business"
            draft_details["business_subtype"] = organization.type.value

    return ApplicationSummary(
        application_id=organization.organization_id,
        organization_id=organization.organization_id,
        name=organization.name,
        status=status,
        review_note=review_note,
        draft_details=draft_details,
    )


def application_write_error(exc: Exception):
    if isinstance(exc, ApplicantNotAllowedError):
        return error_response(403, "FORBIDDEN", "This account cannot modify applications.")
    if isinstance(exc, ApplicationNotFoundError):
        return error_response(404, "NOT_FOUND", "Application not found.")
    if isinstance(exc, ApplicationStateError):
        return error_response(409, "INVALID_STATE_TRANSITION", str(exc))
    if isinstance(exc, ApplicationEvidenceError):
        return error_response(422, "VALIDATION_ERROR", str(exc))
    return error_response(500, "INTERNAL_ERROR", "Unable to update the application.")


APPLICATION_WRITE_ERRORS = (
    ApplicantNotAllowedError,
    ApplicationNotFoundError,
    ApplicationStateError,
    ApplicationEvidenceError,
    SQLAlchemyError,
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

    @router.post("/{application_id}/documents", response_model=ApplicationDocumentResponse, status_code=201)
    def upload_document(
        application_id: ApplicationId,
        document_type: Annotated[DocumentType, Form()],
        file: Annotated[UploadFile, File()],
        applicant: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        try:
            document = save_application_document(
                db, applicant.user_id, application_id, document_type,
                file.filename or "document", file.content_type or "",
                file.file.read(MAX_DOCUMENT_BYTES + 1),
            )
        except APPLICATION_WRITE_ERRORS as exc:
            return application_write_error(exc)
        return ApplicationDocumentResponse(data=document)

    @router.post("/{application_id}/submit", response_model=ApplicationSubmittedResponse)
    def submit(
        application_id: ApplicationId,
        applicant: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        try:
            result = submit_application(db, applicant.user_id, application_id, resubmitting=False)
        except APPLICATION_WRITE_ERRORS as exc:
            return application_write_error(exc)
        return ApplicationSubmittedResponse(data=result)

    @router.post("/{application_id}/resubmit", response_model=ApplicationSubmittedResponse)
    def resubmit(
        application_id: ApplicationId,
        applicant: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        try:
            result = submit_application(db, applicant.user_id, application_id, resubmitting=True)
        except APPLICATION_WRITE_ERRORS as exc:
            return application_write_error(exc)
        return ApplicationSubmittedResponse(data=result)

    return router
