from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.exception_handlers import APIException
from app.db.session import get_engine

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
