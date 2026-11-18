from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.organization import (
    MemberStatus,
    MembershipRole,
    Organization,
    OrganizationMembership,
    VerificationStatus,
)
from app.db.models.organization_document import (
    OrganizationApplicationSubmission,
    OrganizationDocument,
    OrganizationDocumentContent,
)
from app.db.models.status_history import StatusHistory
from app.db.models.user import User
from app.schemas.organization_application import (
    ApplicationDocument,
    ApplicationSubmitted,
    DocumentType,
)
from app.services.organization_application import get_application_details, require_applicant

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
REQUIRED_DOCUMENT_TYPE = "registration_certificate"


class ApplicationNotFoundError(Exception):
    pass


class ApplicationStateError(Exception):
    pass


class ApplicationEvidenceError(Exception):
    pass


def lock_owned_application(db: Session, user_id: int, application_id: int) -> Organization:
    require_applicant(db.get(User, user_id, populate_existing=True, with_for_update=True))
    organization = db.scalar(
        select(Organization)
        .join(OrganizationMembership)
        .where(
            Organization.organization_id == application_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.membership_role == MembershipRole.owner,
            OrganizationMembership.member_status.in_((MemberStatus.invited, MemberStatus.active)),
        )
        .with_for_update(of=Organization)
        .execution_options(populate_existing=True)
    )
    if organization is None:
        raise ApplicationNotFoundError
    return organization


def current_documents(db: Session, application_id: int) -> dict[str, OrganizationDocument]:
    # The newest immutable upload of each type is the current revision.
    rows = db.scalars(
        select(OrganizationDocument)
        .join(OrganizationDocumentContent)
        .where(OrganizationDocument.organization_id == application_id)
        .order_by(OrganizationDocument.document_type, OrganizationDocument.document_id.desc())
        .distinct(OrganizationDocument.document_type)
    )
    return {document.document_type: document for document in rows}


def validate_document(content: bytes, content_type: str) -> None:
    if not content or len(content) > MAX_DOCUMENT_BYTES:
        raise ApplicationEvidenceError("Upload a document between 1 byte and 5 MiB.")
    signatures = {
        "application/pdf": b"%PDF-",
        "image/jpeg": b"\xff\xd8\xff",
        "image/png": b"\x89PNG\r\n\x1a\n",
    }
    signature = signatures.get(content_type)
    if signature is None or not content.startswith(signature):
        raise ApplicationEvidenceError("Upload a PDF, JPEG, or PNG matching the declared file type.")


def save_application_document(
    db: Session,
    user_id: int,
    application_id: int,
    document_type: DocumentType,
    filename: str,
    content_type: str,
    content: bytes,
) -> ApplicationDocument:
    try:
        organization = lock_owned_application(db, user_id, application_id)
        editable_status = (
            VerificationStatus.pending if organization.submitted_at is None
            else VerificationStatus.rejected
        )
        if organization.verification_status != editable_status:
            raise ApplicationStateError("Documents can be uploaded to draft or rejected applications.")
        validate_document(content, content_type)
        previous = current_documents(db, application_id).get(document_type)
        if previous is not None and db.get(OrganizationDocumentContent, previous.document_id).content == content:
            response = ApplicationDocument.model_validate(previous)
            db.rollback()
            return response

        document = OrganizationDocument(
            organization_id=application_id,
            uploaded_by_user_id=user_id,
            document_type=document_type,
            original_filename=filename.replace("\x00", "").replace("\\", "/").rsplit("/", 1)[-1][:255] or "document",
            storage_key=uuid4().hex,
            content_type=content_type,
            file_size_bytes=len(content),
        )
        db.add(document)
        db.flush()
        db.add(OrganizationDocumentContent(document_id=document.document_id, content=content))
        response = ApplicationDocument.model_validate(document)
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


def submit_application(
    db: Session, user_id: int, application_id: int, *, resubmitting: bool
) -> ApplicationSubmitted:
    try:
        organization = lock_owned_application(db, user_id, application_id)
        status = organization.verification_status
        is_draft = organization.submitted_at is None and status == VerificationStatus.pending
        is_rejected = organization.submitted_at is not None and status == VerificationStatus.rejected
        if not (is_rejected if resubmitting else is_draft):
            raise ApplicationStateError(
                "Only rejected applications can be resubmitted." if resubmitting
                else "Only draft applications can be submitted."
            )

        documents = current_documents(db, application_id)
        if REQUIRED_DOCUMENT_TYPE not in documents:
            raise ApplicationEvidenceError("Upload a registration certificate before submitting.")
        document_ids = {kind: doc.document_id for kind, doc in documents.items()}
        if resubmitting:
            previous = db.scalar(
                select(OrganizationApplicationSubmission)
                .where(OrganizationApplicationSubmission.organization_id == application_id)
                .order_by(OrganizationApplicationSubmission.submission_id.desc())
                .limit(1)
            )
            if previous is not None and previous.snapshot["document_ids"] == document_ids:
                raise ApplicationEvidenceError("Upload corrected evidence before resubmitting.")

        submitted_at = datetime.now(timezone.utc)
        organization.submitted_at = submitted_at
        organization.verification_status = VerificationStatus.pending
        organization.updated_at = submitted_at
        organization.verified_by_user_id = None
        organization.verified_at = None
        db.add(OrganizationApplicationSubmission(
            organization_id=application_id,
            submitted_by_user_id=user_id,
            submitted_at=submitted_at,
            snapshot={
                "organization_type": organization.type.value,
                "details": get_application_details(organization),
                "document_ids": document_ids,
            },
        ))
        db.add(StatusHistory(
            entity_type="organization",
            entity_id=application_id,
            old_status="rejected" if resubmitting else "draft",
            new_status="pending_verification",
            changed_by_user_id=user_id,
        ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ApplicationSubmitted(application_id=application_id, organization_id=application_id)
