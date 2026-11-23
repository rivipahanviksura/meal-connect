from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.exception_handlers import APIException
from app.db.session import get_engine
from app.services.application_submission import (
    ApplicationEvidenceError,
    save_application_document,
    submit_application,
)

from app.db.models.user import (
    User,
    UserRole,
    AccountStatus,
)

from app.db.models.organization import (
    Organization,
    OrganizationType,
    OrganizationMembership,
    OrganizationVerification,
    MembershipRole,
    MemberStatus,
    VerificationStatus,
)

from app.db.models.organization_document import (
    OrganizationApplicationSubmission,
    OrganizationDocument,
    OrganizationDocumentContent,
)

from app.db.models.status_history import StatusHistory

from app.services.admin_verification import (
    approve_application,
    reject_application,
    request_application_corrections,
    review_application_document,
)


@pytest.fixture
def db():
    engine = get_engine()

    try:
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            if database_name != "meal_connect_test":
                connection.rollback()
                pytest.fail(
                    "Integration tests require meal_connect_test."
                )

            connection.rollback()
            outer_transaction = connection.begin()

            session = Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            )

            try:
                yield session
            finally:
                session.close()
                outer_transaction.rollback()

    finally:
        engine.dispose()


def create_test_application(db):
    now = datetime.now(timezone.utc)

    admin = User(
        first_name="Test",
        last_name="Admin",
        email="meal89.admin@example.com",
        password_hash="test-only-not-a-real-password",
        role=UserRole.admin,
        account_status=AccountStatus.active,
    )

    applicant = User(
        first_name="Test",
        last_name="Applicant",
        email="meal89.applicant@example.com",
        password_hash="test-only-not-a-real-password",
        role=UserRole.business_staff,
        account_status=AccountStatus.active,
    )

    db.add_all([admin, applicant])
    db.flush()

    organization = Organization(
        name="MEAL89 Test Restaurant",
        type=OrganizationType.restaurant,
        registration_number="MEAL89-TEST-001",
        contact_email="meal89.restaurant@example.com",
        address_line="Test Street",
        city="Colombo",
        representative_name="Test Applicant",
        submitted_at=now,
        verification_status=VerificationStatus.pending,
    )

    db.add(organization)
    db.flush()

    membership = OrganizationMembership(
        organization_id=organization.organization_id,
        user_id=applicant.user_id,
        membership_role=MembershipRole.owner,
        member_status=MemberStatus.active,
    )

    submission = OrganizationApplicationSubmission(
        organization_id=organization.organization_id,
        submitted_by_user_id=applicant.user_id,
        submitted_at=now,
        snapshot={
            "organization_type": "restaurant",
            "details": {},
            "document_ids": {},
        },
    )

    db.add_all([membership, submission])
    db.flush()

    return organization.organization_id, admin.user_id


def test_real_postgres_rejection(db):
    application_id, admin_id = create_test_application(db)

    # Create original registration evidence.
    create_pending_review_document(db, application_id)

    # Find the original application submission.
    original_submission = db.scalar(
        select(OrganizationApplicationSubmission)
        .where(
            OrganizationApplicationSubmission.organization_id
            == application_id
        )
    )


    result = reject_application(
        db=db,
        application_id=application_id,
        admin_id=admin_id,
        reason="Registration evidence requires correction.",
    )

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.rejected
    assert result.data.status == "rejected"
    assert result.data.reviewed_by_user_id == admin_id

    verification = db.scalar(
        select(OrganizationVerification)
        .where(
            OrganizationVerification.organization_id == application_id
        )
    )

    assert verification is not None
    assert verification.decision == VerificationStatus.rejected
    assert verification.reviewed_by_user_id == admin_id

    history = db.scalar(
        select(StatusHistory)
        .where(
            StatusHistory.entity_type == "organization",
            StatusHistory.entity_id == application_id,
            StatusHistory.new_status == "rejected",
        )
    )

    assert history is not None
    assert history.changed_by_user_id == admin_id


def test_real_postgres_duplicate_rejection(db):
    application_id, admin_id = create_test_application(db)

    reason = "Registration evidence requires correction."

    reject_application(
        db=db,
        application_id=application_id,
        admin_id=admin_id,
        reason=reason,
    )

    with pytest.raises(APIException) as error:
        reject_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            reason=reason,
        )

    assert error.value.status_code == 409

    verification_count = db.scalar(
        select(func.count())
        .select_from(OrganizationVerification)
        .where(
            OrganizationVerification.organization_id == application_id
        )
    )

    assert verification_count == 1


def test_real_postgres_request_corrections(db):
    application_id, admin_id = create_test_application(db)

    result = request_application_corrections(
        db=db,
        application_id=application_id,
        admin_id=admin_id,
        reason="Please upload corrected registration evidence.",
    )

    assert result.data.action == "request_corrections"
    assert result.data.status == "rejected"

    verification = db.scalar(
        select(OrganizationVerification)
        .where(
            OrganizationVerification.organization_id == application_id
        )
    )

    assert verification is not None
    assert verification.decision == VerificationStatus.rejected
    assert verification.review_note.startswith(
        "Corrections requested:"
    )

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.rejected


def test_real_postgres_approval_requires_evidence(db):
    application_id, admin_id = create_test_application(db)

    db.commit()

    with pytest.raises(APIException) as error:
        approve_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            comment="Application reviewed for approval.",
        )

    assert error.value.status_code == 422

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.pending
    assert organization.verified_by_user_id is None
    assert organization.verified_at is None

    verification_count = db.scalar(
        select(func.count())
        .select_from(OrganizationVerification)
        .where(
            OrganizationVerification.organization_id == application_id
        )
    )

    assert verification_count == 0


def test_real_postgres_approval_requires_valid_comment(db):
    application_id, admin_id = create_test_application(db)

    db.commit()

    with pytest.raises(APIException) as error:
        approve_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            comment="OK",
        )

    assert error.value.status_code == 422

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.pending
    assert organization.verified_by_user_id is None
    assert organization.verified_at is None


def test_real_postgres_successful_approval(db):
    application_id, admin_id = create_test_application(db)

    submission = db.scalar(
        select(OrganizationApplicationSubmission)
        .where(
            OrganizationApplicationSubmission.organization_id
            == application_id
        )
    )

    assert submission is not None

    document_content = b"%PDF-1.4\nTest content"

    document = OrganizationDocument(
        organization_id=application_id,
        uploaded_by_user_id=submission.submitted_by_user_id,
        document_type="registration_certificate",
        storage_key=uuid4().hex,
        original_filename="test_registration.pdf",
        content_type="application/pdf",
        file_size_bytes=len(document_content),
        review_status="approved",
    )

    db.add(document)
    db.flush()

    db.add(
        OrganizationDocumentContent(
            document_id=document.document_id,
            content=document_content,
        )
    )

    submission.snapshot = {
        "organization_type": "restaurant",
        "details": {},
        "document_ids": {
            "registration_certificate": document.document_id,
        },
    }

    # Record the document review audit required for application approval.
    reviewed_at = datetime.now(timezone.utc)
    document.reviewed_at = reviewed_at

    db.add(
        StatusHistory(
            entity_type="organization_document",
            entity_id=document.document_id,
            old_status="pending",
            new_status="approved",
            changed_by_user_id=admin_id,
            change_reason="Registration evidence reviewed and accepted.",
            changed_at=reviewed_at,
        )
    )

    db.commit()

    result = approve_application(
        db=db,
        application_id=application_id,
        admin_id=admin_id,
        comment="Registration documents reviewed and accepted.",
    )

    assert result.data.action == "approve"
    assert result.data.status == "verified"
    assert result.data.reviewed_by_user_id == admin_id

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.approved
    assert organization.verified_by_user_id == admin_id
    assert organization.verified_at is not None

    verification = db.scalar(
        select(OrganizationVerification)
        .where(
            OrganizationVerification.organization_id
            == application_id
        )
    )

    assert verification is not None
    assert verification.decision == VerificationStatus.approved
    assert verification.reviewed_by_user_id == admin_id

    history = db.scalar(
        select(StatusHistory)
        .where(
            StatusHistory.entity_type == "organization",
            StatusHistory.entity_id == application_id,
            StatusHistory.new_status == "verified",
        )
    )

    assert history is not None
    assert history.changed_by_user_id == admin_id


def test_real_postgres_non_admin_cannot_reject(db):
    application_id, admin_id = create_test_application(db)

    admin = db.get(User, admin_id)
    admin.role = UserRole.business_staff

    db.commit()

    with pytest.raises(APIException) as error:
        reject_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            reason="Registration evidence requires correction.",
        )

    assert error.value.status_code == 403
    assert error.value.code == "FORBIDDEN"

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.pending


def test_real_postgres_inactive_admin_cannot_reject(db):
    application_id, admin_id = create_test_application(db)

    admin = db.get(User, admin_id)
    admin.account_status = AccountStatus.suspended

    db.commit()

    with pytest.raises(APIException) as error:
        reject_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            reason="Registration evidence requires correction.",
        )

    assert error.value.status_code == 403
    assert error.value.code == "FORBIDDEN"

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.pending


def test_real_postgres_non_admin_cannot_approve(db):
    application_id, admin_id = create_test_application(db)

    admin = db.get(User, admin_id)
    admin.role = UserRole.business_staff

    db.commit()

    with pytest.raises(APIException) as error:
        approve_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            comment="Registration documents reviewed and accepted.",
        )

    assert error.value.status_code == 403
    assert error.value.code == "FORBIDDEN"

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.pending

    verification_count = db.scalar(
        select(func.count())
        .select_from(OrganizationVerification)
        .where(
            OrganizationVerification.organization_id
            == application_id
        )
    )

    assert verification_count == 0


def test_real_postgres_inactive_admin_cannot_approve(db):
    application_id, admin_id = create_test_application(db)

    admin = db.get(User, admin_id)
    admin.account_status = AccountStatus.suspended

    db.commit()

    with pytest.raises(APIException) as error:
        approve_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            comment="Registration documents reviewed and accepted.",
        )

    assert error.value.status_code == 403
    assert error.value.code == "FORBIDDEN"

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.pending

    verification_count = db.scalar(
        select(func.count())
        .select_from(OrganizationVerification)
        .where(
            OrganizationVerification.organization_id
            == application_id
        )
    )

    assert verification_count == 0

def test_real_postgres_pending_document_blocks_approval(db):
    application_id, admin_id = create_test_application(db)

    submission = db.scalar(
        select(OrganizationApplicationSubmission).where(
            OrganizationApplicationSubmission.organization_id == application_id
        )
    )
    assert submission is not None

    document_content = b"%PDF-1.4\nTest content"
    document = OrganizationDocument(
        organization_id=application_id,
        uploaded_by_user_id=submission.submitted_by_user_id,
        document_type="registration_certificate",
        storage_key=uuid4().hex,
        original_filename="pending_registration.pdf",
        content_type="application/pdf",
        file_size_bytes=len(document_content),
        review_status="pending",
    )
    db.add(document)
    db.flush()

    db.add(
        OrganizationDocumentContent(
            document_id=document.document_id,
            content=document_content,
        )
    )
    submission.snapshot = {
        "organization_type": "restaurant",
        "details": {},
        "document_ids": {
            "registration_certificate": document.document_id,
        },
    }
    db.commit()

    with pytest.raises(APIException) as error:
        approve_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            comment="Registration documents reviewed and accepted.",
        )

    assert error.value.status_code == 422
    assert error.value.code == "DOCUMENT_NOT_APPROVED"

    organization = db.get(Organization, application_id)
    assert organization is not None
    assert organization.verification_status == VerificationStatus.pending
    assert organization.verified_by_user_id is None
    assert organization.verified_at is None

    verification_count = db.scalar(
        select(func.count())
        .select_from(OrganizationVerification)
        .where(OrganizationVerification.organization_id == application_id)
    )
    assert verification_count == 0


def test_real_postgres_admin_cannot_approve_own_application(db):
    application_id, admin_id = create_test_application(db)

    submission = db.scalar(
        select(OrganizationApplicationSubmission).where(
            OrganizationApplicationSubmission.organization_id
            == application_id
        )
    )

    assert submission is not None

    applicant = db.get(User, submission.submitted_by_user_id)
    assert applicant is not None

    applicant.role = UserRole.admin
    db.commit()

    with pytest.raises(APIException) as error:
        approve_application(
            db=db,
            application_id=application_id,
            admin_id=applicant.user_id,
            comment="Registration documents reviewed and accepted.",
        )

    assert error.value.status_code == 403
    assert error.value.code == "FORBIDDEN"

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.pending


def test_real_postgres_admin_cannot_reject_own_application(db):
    application_id, admin_id = create_test_application(db)

    submission = db.scalar(
        select(OrganizationApplicationSubmission).where(
            OrganizationApplicationSubmission.organization_id
            == application_id
        )
    )

    assert submission is not None

    applicant = db.get(User, submission.submitted_by_user_id)
    assert applicant is not None

    applicant.role = UserRole.admin
    db.commit()

    with pytest.raises(APIException) as error:
        reject_application(
            db=db,
            application_id=application_id,
            admin_id=applicant.user_id,
            reason="Registration evidence requires correction.",
        )

    assert error.value.status_code == 403
    assert error.value.code == "FORBIDDEN"

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.pending


def create_pending_review_document(db, application_id):
    submission = db.scalar(
        select(OrganizationApplicationSubmission).where(
            OrganizationApplicationSubmission.organization_id == application_id
        )
    )
    assert submission is not None

    content = b"%PDF-1.4\nTest registration evidence"
    document = OrganizationDocument(
        organization_id=application_id,
        uploaded_by_user_id=submission.submitted_by_user_id,
        document_type="registration_certificate",
        storage_key=uuid4().hex,
        original_filename="registration.pdf",
        content_type="application/pdf",
        file_size_bytes=len(content),
        review_status="pending",
    )
    db.add(document)
    db.flush()

    db.add(
        OrganizationDocumentContent(
            document_id=document.document_id,
            content=content,
        )
    )

    submission.snapshot = {
        "organization_type": "restaurant",
        "details": {},
        "document_ids": {
            "registration_certificate": document.document_id,
        },
    }
    db.commit()
    return document.document_id


def test_real_postgres_document_approval(db):
    application_id, admin_id = create_test_application(db)
    document_id = create_pending_review_document(db, application_id)

    result = review_application_document(
        db=db,
        application_id=application_id,
        document_id=document_id,
        admin_id=admin_id,
        decision="approved",
        review_note="Registration evidence has been reviewed.",
    )

    assert result["data"]["review_status"] == "approved"
    assert result["data"]["reviewed_by_user_id"] == admin_id

    document = db.get(OrganizationDocument, document_id)
    assert document is not None
    assert document.review_status == "approved"
    assert document.reviewed_at is not None

    history = db.scalar(
        select(StatusHistory).where(
            StatusHistory.entity_type == "organization_document",
            StatusHistory.entity_id == document_id,
        )
    )
    assert history is not None
    assert history.old_status == "pending"
    assert history.new_status == "approved"
    assert history.changed_by_user_id == admin_id


def test_real_postgres_document_rejection(db):
    application_id, admin_id = create_test_application(db)
    document_id = create_pending_review_document(db, application_id)

    result = review_application_document(
        db=db,
        application_id=application_id,
        document_id=document_id,
        admin_id=admin_id,
        decision="rejected",
        review_note="The submitted certificate is incomplete.",
    )

    assert result["data"]["review_status"] == "rejected"
    document = db.get(OrganizationDocument, document_id)
    assert document is not None
    assert document.review_status == "rejected"
    assert document.reviewed_at is not None


def test_real_postgres_duplicate_document_review(db):
    application_id, admin_id = create_test_application(db)
    document_id = create_pending_review_document(db, application_id)

    review_application_document(
        db=db,
        application_id=application_id,
        document_id=document_id,
        admin_id=admin_id,
        decision="approved",
        review_note="Registration certificate reviewed successfully.",
    )

    with pytest.raises(APIException) as error:
        review_application_document(
            db=db,
            application_id=application_id,
            document_id=document_id,
            admin_id=admin_id,
            decision="rejected",
            review_note="Attempting a conflicting document decision.",
        )

    assert error.value.status_code == 409
    assert error.value.code == "DOCUMENT_ALREADY_REVIEWED"

    document = db.get(OrganizationDocument, document_id)
    assert document is not None
    assert document.review_status == "approved"


def test_real_postgres_document_review_requires_admin(db):
    application_id, admin_id = create_test_application(db)
    document_id = create_pending_review_document(db, application_id)

    admin = db.get(User, admin_id)
    assert admin is not None
    admin.role = UserRole.business_staff
    db.commit()

    with pytest.raises(APIException) as error:
        review_application_document(
            db=db,
            application_id=application_id,
            document_id=document_id,
            admin_id=admin_id,
            decision="approved",
            review_note="Registration evidence reviewed successfully.",
        )

    assert error.value.status_code == 403

    document = db.get(OrganizationDocument, document_id)
    assert document is not None
    assert document.review_status == "pending"
    assert document.reviewed_at is None


def test_real_postgres_approval_blocks_missing_document_audit(db):
    application_id, admin_id = create_test_application(db)

    document_id = create_pending_review_document(
        db,
        application_id,
    )

    document = db.get(OrganizationDocument, document_id)
    assert document is not None

    # Simulate an approved document without a review audit record.
    document.review_status = "approved"
    document.reviewed_at = datetime.now(timezone.utc)

    db.commit()

    with pytest.raises(APIException) as error:
        approve_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            comment="Registration evidence reviewed and accepted.",
        )

    assert error.value.status_code == 422
    assert error.value.code == "DOCUMENT_REVIEW_AUDIT_MISSING"

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.pending
    assert organization.verified_by_user_id is None

    verification_count = db.scalar(
        select(func.count())
        .select_from(OrganizationVerification)
        .where(
            OrganizationVerification.organization_id == application_id
        )
    )

    assert verification_count == 0



def test_real_postgres_approval_blocks_type_mismatch(db):
    application_id, admin_id = create_test_application(db)

    document_id = create_pending_review_document(
        db,
        application_id,
    )

    review_application_document(
        db=db,
        application_id=application_id,
        document_id=document_id,
        admin_id=admin_id,
        decision="approved",
        review_note="Registration document reviewed and accepted.",
    )

    submission = db.scalar(
        select(OrganizationApplicationSubmission).where(
            OrganizationApplicationSubmission.organization_id
            == application_id
        )
    )

    assert submission is not None

    snapshot = dict(submission.snapshot)
    snapshot["organization_type"] = "ngo"
    submission.snapshot = snapshot
    db.commit()

    with pytest.raises(APIException) as error:
        approve_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            comment="Registration evidence reviewed and accepted.",
        )

    assert error.value.status_code == 422
    assert error.value.code == "ORGANIZATION_TYPE_MISMATCH"

    organization = db.get(Organization, application_id)

    assert organization is not None
    assert organization.verification_status == VerificationStatus.pending

def prepare_reviewed_category_application(db, organization_type):
    """Create and review registration evidence for an organization category."""
    application_id, admin_id = create_test_application(db)

    organization = db.get(Organization, application_id)
    assert organization is not None
    organization.type = organization_type

    submission = db.scalar(
        select(OrganizationApplicationSubmission).where(
            OrganizationApplicationSubmission.organization_id == application_id
        )
    )
    assert submission is not None

    owner = db.get(User, submission.submitted_by_user_id)
    assert owner is not None
    owner.role = (
        UserRole.ngo_staff
        if organization_type == OrganizationType.ngo
        else UserRole.business_staff
    )

    if organization_type == OrganizationType.ngo:
        organization.registration_authority = "NGO Registration Authority"
        organization.operational_details = {
            "operational_capability": "Food distribution to local communities"
        }

    db.commit()

    document_id = create_pending_review_document(db, application_id)

    snapshot = dict(submission.snapshot)
    snapshot["organization_type"] = organization_type.value
    submission.snapshot = snapshot
    db.commit()

    review_application_document(
        db=db,
        application_id=application_id,
        document_id=document_id,
        admin_id=admin_id,
        decision="approved",
        review_note="Registration evidence was reviewed and accepted.",
    )

    return application_id, admin_id


@pytest.mark.parametrize(
    "organization_type",
    [OrganizationType.bakery, OrganizationType.ngo],
    ids=["bakery", "ngo"],
)
def test_real_postgres_category_approval_with_reviewed_evidence(
    db, organization_type
):
    application_id, admin_id = prepare_reviewed_category_application(
        db, organization_type
    )

    result = approve_application(
        db=db,
        application_id=application_id,
        admin_id=admin_id,
        comment="Organization registration evidence was fully reviewed.",
    )

    organization = db.get(Organization, application_id)
    assert organization is not None
    assert organization.type == organization_type
    assert organization.verification_status == VerificationStatus.approved
    assert result.data.status == "verified"


def test_real_postgres_ngo_requires_registration_authority(db):
    application_id, admin_id = prepare_reviewed_category_application(
        db, OrganizationType.ngo
    )
    organization = db.get(Organization, application_id)
    assert organization is not None
    organization.registration_authority = ""
    db.commit()

    with pytest.raises(APIException) as error:
        approve_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            comment="NGO application evidence has been reviewed.",
        )

    assert error.value.status_code == 422
    assert error.value.code == "VALIDATION_ERROR"
    assert organization.verification_status == VerificationStatus.pending


def test_real_postgres_ngo_requires_operational_capability(db):
    application_id, admin_id = prepare_reviewed_category_application(
        db, OrganizationType.ngo
    )
    organization = db.get(Organization, application_id)
    assert organization is not None
    organization.operational_details = {}
    db.commit()

    with pytest.raises(APIException) as error:
        approve_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            comment="NGO application evidence has been reviewed.",
        )

    assert error.value.status_code == 422
    assert error.value.code == "VALIDATION_ERROR"
    assert organization.verification_status == VerificationStatus.pending


def test_real_postgres_ngo_rejects_business_staff_owner(db):
    application_id, admin_id = prepare_reviewed_category_application(
        db, OrganizationType.ngo
    )
    submission = db.scalar(
        select(OrganizationApplicationSubmission).where(
            OrganizationApplicationSubmission.organization_id == application_id
        )
    )
    assert submission is not None
    owner = db.get(User, submission.submitted_by_user_id)
    assert owner is not None
    owner.role = UserRole.business_staff
    db.commit()

    with pytest.raises(APIException) as error:
        approve_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            comment="NGO application evidence has been reviewed.",
        )

    assert error.value.status_code == 409
    assert error.value.code == "ROLE_MISMATCH"
    organization = db.get(Organization, application_id)
    assert organization is not None
    assert organization.verification_status == VerificationStatus.pending


# MEAL-13: Resubmission must include corrected evidence.
def test_real_postgres_resubmit_requires_corrected_evidence(db):
    application_id, admin_id = create_test_application(db)
    create_pending_review_document(db, application_id)

    reject_application(
        db=db,
        application_id=application_id,
        admin_id=admin_id,
        reason="Registration certificate needs correction.",
    )

    submission = db.scalar(
        select(OrganizationApplicationSubmission)
        .where(
            OrganizationApplicationSubmission.organization_id
            == application_id
        )
    )
    assert submission is not None

    applicant_id = submission.submitted_by_user_id

    with pytest.raises(ApplicationEvidenceError):
        submit_application(
            db=db,
            user_id=applicant_id,
            application_id=application_id,
            resubmitting=True,
        )

    organization = db.get(Organization, application_id)
    assert organization.verification_status == VerificationStatus.rejected


# MEAL-13: Corrected evidence allows resubmission.
def test_real_postgres_resubmit_keeps_organization_and_history(db):
    application_id, admin_id = create_test_application(db)
    original_document_id = create_pending_review_document(
        db, application_id
    )

    original_submission = db.scalar(
        select(OrganizationApplicationSubmission)
        .where(
            OrganizationApplicationSubmission.organization_id
            == application_id
        )
    )
    assert original_submission is not None

    applicant_id = original_submission.submitted_by_user_id
    original_submission_id = original_submission.submission_id

    reject_application(
        db=db,
        application_id=application_id,
        admin_id=admin_id,
        reason="Please provide corrected registration evidence.",
    )

    corrected_document = save_application_document(
        db=db,
        user_id=applicant_id,
        application_id=application_id,
        document_type="registration_certificate",
        filename="corrected_registration.pdf",
        content_type="application/pdf",
        content=b"%PDF-1.4\nCorrected registration evidence",
    )

    assert corrected_document.document_id != original_document_id

    result = submit_application(
        db=db,
        user_id=applicant_id,
        application_id=application_id,
        resubmitting=True,
    )

    assert result.application_id == application_id
    assert result.organization_id == application_id
    assert result.status == "pending_verification"

    organization = db.get(Organization, application_id)
    assert organization.verification_status == VerificationStatus.pending

    submissions = db.scalars(
        select(OrganizationApplicationSubmission)
        .where(
            OrganizationApplicationSubmission.organization_id
            == application_id
        )
        .order_by(OrganizationApplicationSubmission.submission_id)
    ).all()

    assert len(submissions) == 2
    assert submissions[0].submission_id == original_submission_id

    assert (
        submissions[1].snapshot["document_ids"]["registration_certificate"]
        == corrected_document.document_id
    )

    organization_count = db.scalar(
        select(func.count())
        .select_from(Organization)
        .where(Organization.organization_id == application_id)
    )
    assert organization_count == 1



def test_meal13_full_verification_api_workflow(db, monkeypatch):
    from fastapi.testclient import TestClient
    from pydantic import SecretStr

    from app.core.security import create_access_token
    from app.core.config import settings
    from app.db.session import get_db
    from app.main import app

    # JWT secret for testing only
    monkeypatch.setattr(
        settings,
        "secret_key",
        SecretStr("meal13-integration-test-only-secret-key-2026"),
    )


    application_id, admin_id = create_test_application(db)

    # Create original registration evidence
    create_pending_review_document(db, application_id)

    # Get the original submission from the database
    original_submission = db.scalar(
        select(OrganizationApplicationSubmission)
        .where(
            OrganizationApplicationSubmission.organization_id
            == application_id
        )
    )

    assert original_submission is not None




    applicant_id = original_submission.submitted_by_user_id

    admin_headers = {
        "Authorization": f"Bearer {create_access_token(admin_id)}"
    }
    applicant_headers = {
        "Authorization": f"Bearer {create_access_token(applicant_id)}"
    }

    admin_url = (
        f"/api/v1/admin/organization-applications/{application_id}"
    )
    applicant_url = (
        f"/api/v1/organization-applications/{application_id}"
    )

    rejection_reason = (
        "Registration certificate is incomplete. "
        "Please upload a corrected copy."
    )

    original_override = app.dependency_overrides.get(get_db)

    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as client:

            # 1. Admin rejects the application.
            reject_response = client.post(
                f"{admin_url}/reject",
                json={"reason": rejection_reason},
                headers=admin_headers,
            )

            assert reject_response.status_code == 200, (
                reject_response.text
            )

            # 2. Applicant views the rejection reason.
            feedback_response = client.get(
                "/api/v1/organization-applications/me",
                headers=applicant_headers,
            )

            assert feedback_response.status_code == 200, (
                feedback_response.text
            )

            applications = feedback_response.json()["data"]
            assert len(applications) == 1
            assert applications[0]["status"] == "rejected"
            assert applications[0]["review_note"] == rejection_reason

            # 3. Applicant uploads corrected evidence.
            upload_response = client.post(
                f"{applicant_url}/documents",
                headers=applicant_headers,
                data={
                    "document_type": "registration_certificate"
                },
                files={
                    "file": (
                        "corrected_registration.pdf",
                        b"%PDF-1.4\nCorrected registration evidence",
                        "application/pdf",
                    )
                },
            )

            assert upload_response.status_code == 201, (
                upload_response.text
            )

            # 4. Applicant resubmits the same application.
            resubmit_response = client.post(
                f"{applicant_url}/resubmit",
                headers=applicant_headers,
            )

            assert resubmit_response.status_code == 200, (
                resubmit_response.text
            )
            assert (
                resubmit_response.json()["data"]["organization_id"]
                == application_id
            )

            # 5. Organization returns to pending verification.
            db.expire_all()
            organization = db.get(Organization, application_id)

            assert organization is not None
            assert (
                organization.verification_status
                == VerificationStatus.pending
            )

            # 6. Admin retrieves the pending applications queue.
            queue_response = client.get(
                "/api/v1/admin/organization-applications",
                headers=admin_headers,
            )

            assert queue_response.status_code == 200, (
                queue_response.text
            )

            # Find the organization ID within the queue response.
            def contains_application_id(value):
                if isinstance(value, dict):
                    if (
                        value.get("application_id") == application_id
                        or value.get("organization_id") == application_id
                    ):
                        return True

                    return any(
                        contains_application_id(item)
                        for item in value.values()
                    )

                if isinstance(value, list):
                    return any(
                        contains_application_id(item)
                        for item in value
                    )

                return False

            assert contains_application_id(
                queue_response.json()
            ), queue_response.text

    finally:
        if original_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = original_override


@pytest.mark.parametrize(
    "document_type",
    [
        "food_premises_certificate",
        "trade_licence",
    ],
)
def test_meal13_additional_certificate_requires_admin_approval(
    db,
    document_type,
):
    application_id, admin_id = create_test_application(db)

    # The existing test helper prepares approved registration evidence.
    create_pending_review_document(db, application_id)

    submission = db.scalar(
        select(OrganizationApplicationSubmission)
        .where(
            OrganizationApplicationSubmission.organization_id
            == application_id
        )
    )
    assert submission is not None

    applicant_id = submission.submitted_by_user_id

    # The document is uploaded but has not been reviewed.
    document = OrganizationDocument(
        organization_id=application_id,
        uploaded_by_user_id=applicant_id,
        document_type=document_type,
        storage_key=uuid4().hex,
        original_filename=f"{document_type}.pdf",
        content_type="application/pdf",
        file_size_bytes=15,
    )

    db.add(document)
    db.flush()

    db.add(
        OrganizationDocumentContent(
            document_id=document.document_id,
            content=b"%PDF-1.4\nTest",
        )
    )

    snapshot = dict(submission.snapshot)
    document_ids = dict(snapshot["document_ids"])
    document_ids[document_type] = document.document_id
    snapshot["document_ids"] = document_ids
    submission.snapshot = snapshot

    db.flush()

    with pytest.raises(APIException) as exc_info:
        approve_application(
            db=db,
            application_id=application_id,
            admin_id=admin_id,
            comment="All registration evidence reviewed.",
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "DOCUMENT_NOT_APPROVED"
