from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.admin_verification import (
    AdminCorrectionRequest,
    AdminDecisionRequest,
    AdminDecisionResponse,
    AdminDocumentReviewRequest,
    AdminDocumentReviewResponse,
    AdminRejectRequest,
)
from app.services.admin_verification import (
    approve_application,
    reject_application,
    request_application_corrections,
    review_application_document,
)


router = APIRouter(
    prefix="/admin/organization-applications",
    tags=["Admin Verification"],
)


@router.post(
    "/{application_id}/reject",
    response_model=AdminDecisionResponse,
    status_code=200,
)
def reject_organization_application(
    application_id: Annotated[int, Path(gt=0)],
    payload: AdminRejectRequest,
    admin: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    return reject_application(
        db=db,
        application_id=application_id,
        admin_id=admin.user_id,
        reason=payload.reason,
    )


@router.post(
    "/{application_id}/request-corrections",
    response_model=AdminDecisionResponse,
    status_code=200,
    summary="Request corrections to an organization application",
)
def request_organization_corrections(
    application_id: Annotated[int, Path(gt=0)],
    payload: AdminCorrectionRequest,
    admin: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    return request_application_corrections(
        db=db,
        application_id=application_id,
        admin_id=admin.user_id,
        reason=payload.reason,
    )


@router.post(
    "/{application_id}/decision",
    response_model=AdminDecisionResponse,
    status_code=200,
    summary="Review an organization application",
)
def decide_organization_application(
    application_id: Annotated[int, Path(gt=0)],
    payload: AdminDecisionRequest,
    admin: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    if payload.decision == "approved":
        return approve_application(
            db=db,
            application_id=application_id,
            admin_id=admin.user_id,
            comment=payload.review_note,
        )

    if payload.decision == "rejected":
        return reject_application(
            db=db,
            application_id=application_id,
            admin_id=admin.user_id,
            reason=payload.review_note,
        )

    return request_application_corrections(
        db=db,
        application_id=application_id,
        admin_id=admin.user_id,
        reason=payload.review_note,
    )


@router.post(
    "/{application_id}/documents/{document_id}/review",
    response_model=AdminDocumentReviewResponse,
    status_code=200,
    summary="Review a document in a submitted organization application",
)
def review_organization_application_document(
    application_id: Annotated[int, Path(gt=0)],
    document_id: Annotated[int, Path(gt=0)],
    payload: AdminDocumentReviewRequest,
    admin: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    return review_application_document(
        db=db,
        application_id=application_id,
        document_id=document_id,
        admin_id=admin.user_id,
        decision=payload.decision,
        review_note=payload.review_note,
    )
