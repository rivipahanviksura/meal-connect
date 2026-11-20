from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exception_handlers import APIException

from app.db.models.organization import (
    Organization,
    OrganizationType,
    VerificationStatus,
    OrganizationMembership,
    MembershipRole,
    MemberStatus,
    OrganizationVerification,
)

from app.db.models.organization_document import (
    OrganizationApplicationSubmission,
    OrganizationDocument,
    OrganizationDocumentContent,
)

from app.db.models.user import (
    User,
    UserRole,
    AccountStatus,
)
from app.db.models.status_history import StatusHistory
from app.schemas.admin_verification import (
    AdminDecisionData,
    AdminDecisionResponse,
)


def lock_application(
        db: Session,
        application_id: int,
        admin_id: int,
) -> tuple[Organization, OrganizationApplicationSubmission]:
    """
    Load a submitted application and lock it for review.
    The caller must finish with commit or rollback.
    """

    admin = db.get(User, admin_id)

    if (
            admin is None
            or admin.role != UserRole.admin
            or admin.account_status != AccountStatus.active
    ):
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="Only active admins can review applications.",
        )

    organization = db.scalar(
        select(Organization)
        .where(Organization.organization_id == application_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    if organization is None:
        raise APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Application not found.",
        )

    if (
            organization.verification_status != VerificationStatus.pending
            or organization.submitted_at is None
    ):
        raise APIException(
            status_code=409,
            code="INVALID_STATE_TRANSITION",
            message="Application is not awaiting review.",
        )

    submission = db.scalar(
        select(OrganizationApplicationSubmission)
        .where(
            OrganizationApplicationSubmission.organization_id
            == application_id
        )
        .order_by(
            OrganizationApplicationSubmission.submission_id.desc()
        )
        .limit(1)
    )

    if submission is None:
        raise APIException(
            status_code=409,
            code="INVALID_STATE_TRANSITION",
            message="No submitted application was found.",
        )

    if submission.submitted_by_user_id == admin_id:
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="You cannot review your own application.",
        )

    applicant_membership = db.scalar(
        select(OrganizationMembership.membership_id)
        .where(
            OrganizationMembership.organization_id == application_id,
            OrganizationMembership.user_id == admin_id,
        )
        .limit(1)
    )

    if applicant_membership is not None:
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="You cannot review your own organization.",
        )

    return organization, submission


def check_registration_evidence(
        db: Session,
        organization: Organization,
        submission: OrganizationApplicationSubmission,
) -> None:
    """
    Check that registration evidence exists in the
    submitted application snapshot.
    """

    snapshot = submission.snapshot

    if not isinstance(snapshot, dict):
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Application submission evidence is invalid.",
        )


    # Ensure submitted organization type matches the database record.
    submitted_type = snapshot.get("organization_type")

    if (
        not isinstance(submitted_type, str)
        or submitted_type != organization.type.value
    ):
        raise APIException(
            status_code=422,
            code="ORGANIZATION_TYPE_MISMATCH",
            message="Submitted organization type does not match the application.",
            fields=[
                {
                    "field": "organization_type",
                    "message": "Organization type is inconsistent.",
                    "code": "organization_type_mismatch",
                }
            ],
        )

    document_ids = snapshot.get("document_ids")

    if not isinstance(document_ids, dict):
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Application documents are missing.",
        )

    registration_id = document_ids.get("registration_certificate")

    if not isinstance(registration_id, int) or registration_id <= 0:
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Registration certificate is required.",
        )

    document = db.scalar(
        select(OrganizationDocument)
        .join(
            OrganizationDocumentContent,
            OrganizationDocument.document_id
            == OrganizationDocumentContent.document_id,
        )
        .where(
            OrganizationDocument.document_id == registration_id,
            OrganizationDocument.organization_id
            == organization.organization_id,
            OrganizationDocument.document_type
            == "registration_certificate",
            OrganizationDocument.file_size_bytes > 0,
        )
    )

    if document is None:
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Valid registration evidence was not found.",
        )

    if document.review_status != "approved":
        raise APIException(
            status_code=422,
            code="DOCUMENT_NOT_APPROVED",
            message="Registration evidence must be reviewed and approved.",
            fields=[
                {
                    "field": "registration_certificate",
                    "message": "Document review is not complete.",
                    "code": "document_not_approved",
                }
            ],
        )

    # Require an audit entry for the approved registration document.
    approval_history = db.scalar(
        select(StatusHistory.status_history_id)
        .where(
            StatusHistory.entity_type == "organization_document",
            StatusHistory.entity_id == document.document_id,
            StatusHistory.old_status == "pending",
            StatusHistory.new_status == "approved",
        )
        .limit(1)
    )

    if document.reviewed_at is None or approval_history is None:
        raise APIException(
            status_code=422,
            code="DOCUMENT_REVIEW_AUDIT_MISSING",
            message="Document approval audit information is missing.",
            fields=[
                {
                    "field": "registration_certificate",
                    "message": "A recorded Admin review is required.",
                    "code": "document_review_audit_missing",
                }
            ],
        )

    if organization.type not in {
        OrganizationType.restaurant,
        OrganizationType.bakery,
        OrganizationType.ngo,
    }:
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Unsupported organization type.",
        )


def reject_application(
        db: Session,
        application_id: int,
        admin_id: int,
        reason: str,
) -> AdminDecisionResponse:
    reason = reason.strip()

    if len(reason) < 10 or len(reason) > 2000:
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message="A meaningful rejection reason is required.",
            fields=[
                {
                    "field": "reason",
                    "message": "Reason must contain 10 to 2000 characters.",
                    "code": "invalid_reason",
                }
            ],
        )

    try:
        organization, submission = lock_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
        )

        reviewed_at = datetime.now(timezone.utc)

        organization.verification_status = VerificationStatus.rejected
        organization.verified_by_user_id = None
        organization.verified_at = None
        organization.updated_at = reviewed_at

        db.add(
            OrganizationVerification(
                organization_id=organization.organization_id,
                reviewed_by_user_id=admin_id,
                decision=VerificationStatus.rejected,
                review_note=reason,
                reviewed_at=reviewed_at,
            )
        )

        db.add(
            StatusHistory(
                entity_type="organization",
                entity_id=organization.organization_id,
                old_status="pending_verification",
                new_status="rejected",
                changed_by_user_id=admin_id,
                change_reason=reason,
                changed_at=reviewed_at,
            )
        )

        result = AdminDecisionResponse(
            data=AdminDecisionData(
                application_id=application_id,
                organization_id=organization.organization_id,
                action="reject",
                status="rejected",
                reviewed_by_user_id=admin_id,
                reviewed_at=reviewed_at,
                reason=reason,
            )
        )

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def validate_organization_details(
        organization: Organization,
) -> None:
    """Check required organization information before approval."""

    required_fields = {
        "name": organization.name,
        "registration_number": organization.registration_number,
        "contact_email": organization.contact_email,
        "address_line": organization.address_line,
        "city": organization.city,
        "representative_name": organization.representative_name,
    }

    missing_fields = [
        field
        for field, value in required_fields.items()
        if not isinstance(value, str) or not value.strip()
    ]

    if organization.type == OrganizationType.ngo:
        if not organization.registration_authority:
            missing_fields.append("registration_authority")

        operational = organization.operational_details

        if not isinstance(operational, dict) or not operational.get(
                "operational_capability"
        ):
            missing_fields.append("operational_capability")

    if missing_fields:
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Required organization information is missing.",
            fields=[
                {
                    "field": field,
                    "message": "This field is required for approval.",
                    "code": "required",
                }
                for field in missing_fields
            ],
        )


def request_application_corrections(
        db: Session,
        application_id: int,
        admin_id: int,
        reason: str,
) -> AdminDecisionResponse:
    """
    Request corrections using the existing
    rejected -> resubmit application workflow.
    """

    reason = reason.strip()

    if len(reason) < 10 or len(reason) > 2000:
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message="A meaningful correction reason is required.",
            fields=[
                {
                    "field": "reason",
                    "message": "Reason must contain 10 to 2000 characters.",
                    "code": "invalid_reason",
                }
            ],
        )

    try:
        organization, submission = lock_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
        )

        reviewed_at = datetime.now(timezone.utc)

        organization.verification_status = VerificationStatus.rejected
        organization.verified_by_user_id = None
        organization.verified_at = None
        organization.updated_at = reviewed_at

        review_note = f"Corrections requested: {reason}"

        db.add(
            OrganizationVerification(
                organization_id=organization.organization_id,
                reviewed_by_user_id=admin_id,
                decision=VerificationStatus.rejected,
                review_note=review_note,
                reviewed_at=reviewed_at,
            )
        )

        db.add(
            StatusHistory(
                entity_type="organization",
                entity_id=organization.organization_id,
                old_status="pending_verification",
                new_status="rejected",
                changed_by_user_id=admin_id,
                change_reason=review_note,
                changed_at=reviewed_at,
            )
        )

        result = AdminDecisionResponse(
            data=AdminDecisionData(
                application_id=application_id,
                organization_id=organization.organization_id,
                action="request_corrections",
                status="rejected",
                reviewed_by_user_id=admin_id,
                reviewed_at=reviewed_at,
                reason=reason,
            )
        )

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def validate_approval_membership(
        db: Session,
        organization: Organization,
        submission: OrganizationApplicationSubmission,
) -> None:
    """
    Check applicant ownership, account status,
    and organization-role consistency.
    """

    membership = db.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id
            == organization.organization_id,
            OrganizationMembership.membership_role
            == MembershipRole.owner,
            OrganizationMembership.member_status
            == MemberStatus.active,
        )
    )

    if membership is None:
        raise APIException(
            status_code=409,
            code="INVALID_MEMBERSHIP",
            message="An active organization owner is required.",
        )

    if membership.user_id != submission.submitted_by_user_id:
        raise APIException(
            status_code=409,
            code="APPLICANT_MISMATCH",
            message="Application ownership is inconsistent.",
        )

    owner = db.get(User, membership.user_id)

    if owner is None or owner.account_status != AccountStatus.active:
        raise APIException(
            status_code=409,
            code="INACTIVE_APPLICANT",
            message="The applicant account must be active.",
        )

    expected_role = (
        UserRole.ngo_staff
        if organization.type == OrganizationType.ngo
        else UserRole.business_staff
    )

    if owner.role != expected_role:
        raise APIException(
            status_code=409,
            code="ROLE_MISMATCH",
            message="Applicant role does not match organization type.",
        )

    other_membership = db.scalar(
        select(OrganizationMembership.membership_id)
        .where(
            OrganizationMembership.user_id == owner.user_id,
            OrganizationMembership.organization_id
            != organization.organization_id,
            OrganizationMembership.member_status
            != MemberStatus.removed,
        )
        .limit(1)
    )

    if other_membership is not None:
        raise APIException(
            status_code=409,
            code="MULTIPLE_ORGANIZATIONS",
            message="Applicant is linked to another organization.",
        )

def approve_application(
    db: Session,
    application_id: int,
    admin_id: int,
    comment: str,
) -> AdminDecisionResponse:
    """
    Approve a submitted organization application.

    Caller must be an active Admin.
    Approval and audit records are committed atomically.
    """

    comment = comment.strip()

    if len(comment) < 10 or len(comment) > 2000:
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Approval review notes are required.",
            fields=[
                {
                    "field": "comment",
                    "message": "Provide 10 to 2000 characters of review notes.",
                    "code": "invalid_comment",
                }
            ],
        )

    try:
        organization, submission = lock_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
        )

        validate_organization_details(organization)

        check_registration_evidence(
            db=db,
            organization=organization,
            submission=submission,
        )

        validate_approval_membership(
            db=db,
            organization=organization,
            submission=submission,
        )

        reviewed_at = datetime.now(timezone.utc)

        organization.verification_status = VerificationStatus.approved
        organization.verified_by_user_id = admin_id
        organization.verified_at = reviewed_at
        organization.updated_at = reviewed_at

        db.add(
            OrganizationVerification(
                organization_id=organization.organization_id,
                reviewed_by_user_id=admin_id,
                decision=VerificationStatus.approved,
                review_note=comment,
                reviewed_at=reviewed_at,
            )
        )

        db.add(
            StatusHistory(
                entity_type="organization",
                entity_id=organization.organization_id,
                old_status="pending_verification",
                new_status="verified",
                changed_by_user_id=admin_id,
                change_reason=comment,
                changed_at=reviewed_at,
            )
        )

        result = AdminDecisionResponse(
            data=AdminDecisionData(
                application_id=application_id,
                organization_id=organization.organization_id,
                action="approve",
                status="verified",
                reviewed_by_user_id=admin_id,
                reviewed_at=reviewed_at,
                reason=comment,
            )
        )

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def review_application_document(
    db: Session,
    application_id: int,
    document_id: int,
    admin_id: int,
    decision: str,
    review_note: str,
) -> dict:
    """
    Review a document belonging to the current
    submitted organization application.
    """

    review_note = review_note.strip()

    if decision not in {"approved", "rejected"}:
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Invalid document review decision.",
        )

    if len(review_note) < 10 or len(review_note) > 2000:
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message="A review note of 10 to 2000 characters is required.",
        )

    try:
        organization, submission = lock_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
        )

        snapshot = submission.snapshot

        if not isinstance(snapshot, dict):
            raise APIException(
                status_code=409,
                code="INVALID_SUBMISSION",
                message="Submitted application snapshot is invalid.",
            )

        # Ensure submitted organization type matches the database record.
        submitted_type = snapshot.get("organization_type")

        if (
                not isinstance(submitted_type, str)
                or submitted_type != organization.type.value
        ):
            raise APIException(
                status_code=422,
                code="ORGANIZATION_TYPE_MISMATCH",
                message="Submitted organization type does not match the application.",
                fields=[
                    {
                        "field": "organization_type",
                        "message": "Organization type is inconsistent.",
                        "code": "organization_type_mismatch",
                    }
                ],
            )

        document_ids = snapshot.get("document_ids")

        if not isinstance(document_ids, dict):
            raise APIException(
                status_code=409,
                code="INVALID_SUBMISSION",
                message="Submitted document references are invalid.",
            )

        if document_id not in document_ids.values():
            raise APIException(
                status_code=404,
                code="NOT_FOUND",
                message="Document not found in the current submission.",
            )

        document = db.scalar(
            select(OrganizationDocument)
            .where(
                OrganizationDocument.document_id == document_id,
                OrganizationDocument.organization_id
                == organization.organization_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        if document is None:
            raise APIException(
                status_code=404,
                code="NOT_FOUND",
                message="Document not found.",
            )

        if (
            document.document_type not in document_ids
            or document_ids[document.document_type] != document_id
        ):
            raise APIException(
                status_code=409,
                code="INVALID_DOCUMENT_VERSION",
                message="Document does not match the submitted version.",
            )

        if document.review_status != "pending":
            raise APIException(
                status_code=409,
                code="DOCUMENT_ALREADY_REVIEWED",
                message="Document has already been reviewed.",
            )

        # An approval must refer to evidence that is actually stored.
        # Rejecting an unreadable document remains possible so the
        # applicant can correct it through the existing workflow.
        if decision == "approved":
            document_content = db.scalar(
                select(OrganizationDocumentContent).where(
                    OrganizationDocumentContent.document_id == document_id
                )
            )
            content = (
                document_content.content
                if document_content is not None
                else None
            )
            if (
                not isinstance(content, bytes)
                or not content
                or document.file_size_bytes != len(content)
            ):
                raise APIException(
                    status_code=422,
                    code="INVALID_DOCUMENT_CONTENT",
                    message="Document content is missing or inconsistent.",
                )

        reviewed_at = datetime.now(timezone.utc)

        previous_status = document.review_status

        document.review_status = decision
        document.reviewed_at = reviewed_at

        db.add(
            StatusHistory(
                entity_type="organization_document",
                entity_id=document.document_id,
                old_status=previous_status,
                new_status=decision,
                changed_by_user_id=admin_id,
                change_reason=review_note,
                changed_at=reviewed_at,
            )
        )

        result = {
            "data": {
                "application_id": application_id,
                "document_id": document.document_id,
                "review_status": decision,
                "reviewed_by_user_id": admin_id,
                "reviewed_at": reviewed_at.isoformat(),
                "review_note": review_note,
            }
        }

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise
