from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.db.models.organization import (
    Organization,
    OrganizationVerification,
    VerificationStatus,
)
from app.db.models.organization_document import (
    OrganizationApplicationSubmission,
    OrganizationDocument,
)
from app.db.models.status_history import StatusHistory
from app.db.models.user import User
from app.schemas.admin_organization_application import (
    AdminApplicationDetail,
    AdminApplicationDocument,
    AdminApplicationPagination,
    AdminApplicationQueueItem,
    AdminApplicationQueueQuery,
    AdminApplicationQueueResponse,
    AdminApplicationReviewHistory,
    AdminApplicationStatusHistory,
    AdminApplicationSubmissionHistory,
)


class AdminApplicationNotFoundError(Exception):
    pass


def list_admin_applications(
    db: Session,
    filters: AdminApplicationQueueQuery,
) -> AdminApplicationQueueResponse:
    conditions = [
        Organization.submitted_at.is_not(None),
        Organization.verification_status == VerificationStatus(filters.status),
    ]

    if filters.organization_type is not None:
        conditions.append(
            Organization.type == filters.organization_type
        )

    total_items = db.scalar(
        select(func.count(Organization.organization_id)).where(*conditions)
    ) or 0

    organizations = db.scalars(
        select(Organization)
        .where(*conditions)
        .order_by(
            Organization.submitted_at.desc(),
            Organization.organization_id.desc(),
        )
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    ).all()

    data = [
        AdminApplicationQueueItem(
            application_id=organization.organization_id,
            organization_id=organization.organization_id,
            organization_name=organization.name,
            organization_type=organization.type.value,
            registration_number=organization.registration_number,
            submitted_at=organization.submitted_at,
            verification_status=organization.verification_status.value,
        )
        for organization in organizations
    ]

    return AdminApplicationQueueResponse(
        data=data,
        pagination=AdminApplicationPagination(
            page=filters.page,
            page_size=filters.page_size,
            total_items=total_items,
            total_pages=ceil(total_items / filters.page_size) if total_items else 0,
        ),
    )


def get_admin_application_detail(
    db: Session,
    application_id: int,
) -> AdminApplicationDetail:
    organization = db.scalar(
        select(Organization).where(
            Organization.organization_id == application_id,
            Organization.submitted_at.is_not(None),
        )
    )

    if organization is None:
        raise AdminApplicationNotFoundError

    documents = db.scalars(
        select(OrganizationDocument)
        .where(OrganizationDocument.organization_id == application_id)
        .order_by(
            OrganizationDocument.uploaded_at.desc(),
            OrganizationDocument.document_id.desc(),
        )
    ).all()

    submissions = db.scalars(
        select(OrganizationApplicationSubmission)
        .where(OrganizationApplicationSubmission.organization_id == application_id)
        .order_by(
            OrganizationApplicationSubmission.submitted_at.desc(),
            OrganizationApplicationSubmission.submission_id.desc(),
        )
    ).all()

    reviewer = aliased(User)
    reviews = db.execute(
        select(OrganizationVerification, reviewer)
        .join(reviewer, reviewer.user_id == OrganizationVerification.reviewed_by_user_id)
        .where(OrganizationVerification.organization_id == application_id)
        .order_by(
            OrganizationVerification.reviewed_at.desc(),
            OrganizationVerification.verification_id.desc(),
        )
    ).all()

    changer = aliased(User)
    status_changes = db.execute(
        select(StatusHistory, changer)
        .outerjoin(changer, changer.user_id == StatusHistory.changed_by_user_id)
        .where(
            StatusHistory.entity_type == "organization",
            StatusHistory.entity_id == application_id,
        )
        .order_by(
            StatusHistory.changed_at.desc(),
            StatusHistory.status_history_id.desc(),
        )
    ).all()

    return AdminApplicationDetail(
        application_id=organization.organization_id,
        organization_id=organization.organization_id,
        name=organization.name,
        organization_type=organization.type.value,
        registration_number=organization.registration_number,
        contact_email=organization.contact_email,
        contact_phone=organization.contact_phone,
        address_line=organization.address_line,
        city=organization.city,
        district=organization.district,
        registration_authority=organization.registration_authority,
        registration_date=organization.registration_date,
        registration_expiry_date=organization.registration_expiry_date,
        representative_name=organization.representative_name,
        representative_designation=organization.representative_designation,
        pickup_location=organization.pickup_location,
        operational_details=organization.operational_details,
        submitted_at=organization.submitted_at,
        verification_status=organization.verification_status.value,
        documents=[
            AdminApplicationDocument(
                document_id=document.document_id,
                document_type=document.document_type,
                original_filename=document.original_filename,
                content_type=document.content_type,
                file_size_bytes=document.file_size_bytes,
                review_status=document.review_status,
                uploaded_at=document.uploaded_at,
            )
            for document in documents
        ],
        submissions=[
            AdminApplicationSubmissionHistory(
                submission_id=submission.submission_id,
                submitted_at=submission.submitted_at,
                snapshot=submission.snapshot,
            )
            for submission in submissions
        ],
        reviews=[
            AdminApplicationReviewHistory(
                verification_id=verification.verification_id,
                decision=verification.decision.value,
                review_note=verification.review_note,
                reviewed_at=verification.reviewed_at,
                reviewer_name=f"{user.first_name} {user.last_name}",
            )
            for verification, user in reviews
        ],
        status_history=[
            AdminApplicationStatusHistory(
                status_history_id=history.status_history_id,
                old_status=history.old_status,
                new_status=history.new_status,
                change_reason=history.change_reason,
                changed_at=history.changed_at,
                changed_by_name=(
                    f"{user.first_name} {user.last_name}" if user else None
                ),
            )
            for history, user in status_changes
        ],
    )


def get_admin_document_content(
    db: Session,
    application_id: int,
    document_id: int,
) -> tuple[OrganizationDocument, bytes]:
    from app.db.models.organization_document import OrganizationDocumentContent

    document_and_content = db.execute(
        select(OrganizationDocument, OrganizationDocumentContent.content)
        .join(
            OrganizationDocumentContent,
            OrganizationDocumentContent.document_id
            == OrganizationDocument.document_id,
        )
        .join(
            Organization,
            Organization.organization_id == OrganizationDocument.organization_id,
        )
        .where(
            Organization.organization_id == application_id,
            Organization.submitted_at.is_not(None),
            OrganizationDocument.document_id == document_id,
        )
    ).one_or_none()

    if document_and_content is None:
        raise AdminApplicationNotFoundError

    return document_and_content[0], document_and_content[1]
