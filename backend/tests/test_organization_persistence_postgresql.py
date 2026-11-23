from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.organization import (
    MemberStatus,
    MembershipRole,
    Organization,
    OrganizationMembership,
    OrganizationType,
    VerificationStatus,
)
from app.db.models.user import AccountStatus, User, UserRole
from app.db.session import get_engine
from app.schemas.organization_application import (
    BusinessApplication,
    NgoApplication,
)
from app.services.organization_application import (
    ApplicationAlreadyExistsError,
    RegistrationNumberAlreadyExistsError,
    create_application_draft,
    get_own_application,
)


@pytest.fixture
def db():
    assert settings.database_url is not None

    url = make_url(settings.database_url.get_secret_value())

    assert url.get_backend_name() == "postgresql"
    assert url.database == "meal_connect_test"
    assert url.host in {"localhost", "127.0.0.1", "::1"}

    engine = get_engine()

    try:
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()
            assert database_name == "meal_connect_test"

            connection.rollback()
            transaction = connection.begin()

            session = Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
            )

            try:
                yield session
            finally:
                session.close()
                transaction.rollback()
    finally:
        engine.dispose()


def create_applicant(db, role):
    unique_id = uuid4().hex

    user = User(
        first_name="Application",
        last_name="Test",
        email=f"meal214_{unique_id}@example.com",
        password_hash="test-only-placeholder",
        role=role,
        account_status=AccountStatus.active,
    )

    db.add(user)
    db.flush()
    user_id = user.user_id
    db.commit()

    return user_id


def make_application(kind, registration_number=None):
    unique_id = uuid4().hex

    details = {
        "name": f"Test Organization {unique_id}",
        "registration_number": (
            registration_number or f"MEAL214-{unique_id}"
        ),
        "contact_email": f"org_{unique_id}@example.com",
        "address_line": "Test address",
        "city": "Kurunegala",
        "representative_name": "Test Representative",
    }

    if kind == "ngo":
        return NgoApplication(
            **details,
            organization_type="ngo",
            registration_authority="Test Authority",
        )

    return BusinessApplication(
        **details,
        organization_type="business",
        business_subtype=kind,
    )


def count_rows(db, model):
    return db.scalar(
        select(func.count()).select_from(model)
    )


@pytest.mark.parametrize(
    "kind, role, expected_type",
    [
        (
            "restaurant",
            UserRole.business_staff,
            OrganizationType.restaurant,
        ),
        (
            "bakery",
            UserRole.business_staff,
            OrganizationType.bakery,
        ),
        (
            "ngo",
            UserRole.ngo_staff,
            OrganizationType.ngo,
        ),
    ],
)
def test_draft_links_correct_account_without_activating_membership(
    db,
    kind,
    role,
    expected_type,
):
    user_id = create_applicant(db, role)
    request = make_application(kind)

    result = create_application_draft(
        db,
        user_id,
        request,
    )

    assert result.application_id == result.organization_id
    assert result.status == "draft"

    organization = db.get(
        Organization,
        result.organization_id,
    )

    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id
            == result.organization_id
        )
    )

    assert organization.type == expected_type
    assert organization.name == request.name
    assert organization.verification_status == VerificationStatus.pending
    assert organization.submitted_at is None

    assert membership is not None
    assert membership.user_id == user_id
    assert membership.membership_role == MembershipRole.owner
    assert membership.member_status == MemberStatus.invited

    own_application = get_own_application(db, user_id)

    assert own_application is not None
    assert own_application.organization_id == result.organization_id


def test_same_applicant_cannot_create_second_organization(db):
    user_id = create_applicant(db, UserRole.ngo_staff)

    first = create_application_draft(
        db,
        user_id,
        make_application("ngo"),
    )

    organization_count = count_rows(db, Organization)
    membership_count = count_rows(db, OrganizationMembership)

    with pytest.raises(ApplicationAlreadyExistsError):
        create_application_draft(
            db,
            user_id,
            make_application("ngo"),
        )

    assert count_rows(db, Organization) == organization_count
    assert count_rows(db, OrganizationMembership) == membership_count
    assert get_own_application(db, user_id).organization_id == (
        first.organization_id
    )


def test_other_applicant_cannot_read_application_through_own_lookup(db):
    owner_id = create_applicant(db, UserRole.ngo_staff)
    other_id = create_applicant(db, UserRole.ngo_staff)

    result = create_application_draft(
        db,
        owner_id,
        make_application("ngo"),
    )

    assert get_own_application(db, other_id) is None
    assert get_own_application(db, owner_id).organization_id == (
        result.organization_id
    )


def test_duplicate_registration_number_rolls_back_and_allows_retry(db):
    first_user_id = create_applicant(db, UserRole.ngo_staff)
    second_user_id = create_applicant(db, UserRole.ngo_staff)

    registration_number = f"MEAL214-{uuid4().hex}"

    create_application_draft(
        db,
        first_user_id,
        make_application("ngo", registration_number),
    )

    organization_count = count_rows(db, Organization)
    membership_count = count_rows(db, OrganizationMembership)

    with pytest.raises(RegistrationNumberAlreadyExistsError):
        create_application_draft(
            db,
            second_user_id,
            make_application("ngo", registration_number),
        )

    assert count_rows(db, Organization) == organization_count
    assert count_rows(db, OrganizationMembership) == membership_count
    assert get_own_application(db, second_user_id) is None

    retry = create_application_draft(
        db,
        second_user_id,
        make_application("ngo"),
    )

    assert get_own_application(db, second_user_id).organization_id == (
        retry.organization_id
    )


def test_commit_failure_leaves_no_orphan_organization(db, monkeypatch):
    user_id = create_applicant(db, UserRole.ngo_staff)

    organization_count = count_rows(db, Organization)
    membership_count = count_rows(db, OrganizationMembership)

    with monkeypatch.context() as patch:
        patch.setattr(
            db,
            "commit",
            Mock(
                side_effect=SQLAlchemyError(
                    "Simulated commit failure"
                )
            ),
        )

        with pytest.raises(SQLAlchemyError):
            create_application_draft(
                db,
                user_id,
                make_application("ngo"),
            )

    assert count_rows(db, Organization) == organization_count
    assert count_rows(db, OrganizationMembership) == membership_count
    assert get_own_application(db, user_id) is None

    retry = create_application_draft(
        db,
        user_id,
        make_application("ngo"),
    )

    assert retry.organization_id is not None



from datetime import datetime, timezone

from app.db.models.organization_document import (
    OrganizationApplicationSubmission,
    OrganizationDocument,
    OrganizationDocumentContent,
)
from app.services.application_submission import (
    ApplicationEvidenceError,
    save_application_document,
    submit_application,
)


# Synthetic bytes for persistence tests only.
# These are not full PDF-format validation tests.
FIRST_EVIDENCE = b"%PDF-1.4\nMEAL214 original test evidence"
CORRECTED_EVIDENCE = b"%PDF-1.4\nMEAL214 corrected test evidence"


def create_test_draft(db):
    user_id = create_applicant(db, UserRole.ngo_staff)

    draft = create_application_draft(
        db,
        user_id,
        make_application("ngo"),
    )

    return user_id, draft.organization_id


def upload_test_evidence(db, user_id, organization_id, content):
    return save_application_document(
        db=db,
        user_id=user_id,
        application_id=organization_id,
        document_type="registration_certificate",
        filename="test-certificate.pdf",
        content_type="application/pdf",
        content=content,
    )


def get_submission_records(db, organization_id):
    return db.scalars(
        select(OrganizationApplicationSubmission)
        .where(
            OrganizationApplicationSubmission.organization_id
            == organization_id
        )
        .order_by(
            OrganizationApplicationSubmission.submission_id
        )
    ).all()


def test_failed_upload_preserves_draft_and_can_be_retried(db):
    user_id, organization_id = create_test_draft(db)
    original_name = db.get(Organization, organization_id).name

    with pytest.raises(ApplicationEvidenceError):
        upload_test_evidence(
            db,
            user_id,
            organization_id,
            b"invalid-document-content",
        )

    db.expire_all()

    organization = get_own_application(db, user_id)

    assert organization.organization_id == organization_id
    assert organization.name == original_name
    assert organization.verification_status == VerificationStatus.pending
    assert organization.submitted_at is None

    documents = db.scalars(
        select(OrganizationDocument).where(
            OrganizationDocument.organization_id
            == organization_id
        )
    ).all()

    assert documents == []

    uploaded = upload_test_evidence(
        db,
        user_id,
        organization_id,
        FIRST_EVIDENCE,
    )

    assert uploaded.document_id is not None
    assert get_own_application(db, user_id).organization_id == (
        organization_id
    )


def test_submission_requires_evidence_and_persists_snapshot(db):
    user_id, organization_id = create_test_draft(db)

    with pytest.raises(ApplicationEvidenceError):
        submit_application(
            db,
            user_id,
            organization_id,
            resubmitting=False,
        )

    db.expire_all()

    organization = db.get(Organization, organization_id)

    assert organization.submitted_at is None
    assert get_submission_records(db, organization_id) == []

    uploaded = upload_test_evidence(
        db,
        user_id,
        organization_id,
        FIRST_EVIDENCE,
    )

    result = submit_application(
        db,
        user_id,
        organization_id,
        resubmitting=False,
    )

    db.expire_all()

    organization = db.get(Organization, organization_id)
    submissions = get_submission_records(db, organization_id)

    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id
            == organization_id
        )
    )

    assert result.status == "pending_verification"
    assert organization.submitted_at is not None
    assert organization.verification_status == VerificationStatus.pending

    # Submission must not activate organization membership.
    assert membership.member_status == MemberStatus.invited

    assert len(submissions) == 1
    assert submissions[0].submitted_by_user_id == user_id
    assert submissions[0].submitted_at is not None
    assert submissions[0].snapshot["document_ids"] == {
        "registration_certificate": uploaded.document_id
    }


def test_resubmission_preserves_organization_and_previous_evidence(db):
    user_id, organization_id = create_test_draft(db)

    first_document = upload_test_evidence(
        db,
        user_id,
        organization_id,
        FIRST_EVIDENCE,
    )

    submit_application(
        db,
        user_id,
        organization_id,
        resubmitting=False,
    )

    # Set up a rejected state only.
    # This does not test the Admin decision workflow.
    organization = db.get(Organization, organization_id)
    organization.verification_status = VerificationStatus.rejected
    organization.verified_by_user_id = user_id
    organization.verified_at = datetime.now(timezone.utc)
    db.commit()

    organization_count = count_rows(db, Organization)
    membership_count = count_rows(db, OrganizationMembership)

    # Unchanged evidence must not create another submission.
    with pytest.raises(ApplicationEvidenceError):
        submit_application(
            db,
            user_id,
            organization_id,
            resubmitting=True,
        )

    assert len(get_submission_records(db, organization_id)) == 1

    corrected_document = upload_test_evidence(
        db,
        user_id,
        organization_id,
        CORRECTED_EVIDENCE,
    )

    result = submit_application(
        db,
        user_id,
        organization_id,
        resubmitting=True,
    )

    db.expire_all()

    organization = db.get(Organization, organization_id)
    submissions = get_submission_records(db, organization_id)

    assert result.organization_id == organization_id
    assert count_rows(db, Organization) == organization_count
    assert count_rows(db, OrganizationMembership) == membership_count

    assert organization.verification_status == VerificationStatus.pending
    assert organization.verified_by_user_id is None
    assert organization.verified_at is None

    assert len(submissions) == 2
    assert submissions[0].snapshot["document_ids"] == {
        "registration_certificate": first_document.document_id
    }
    assert submissions[1].snapshot["document_ids"] == {
        "registration_certificate": corrected_document.document_id
    }

    # Both immutable document revisions must remain stored.
    original_content = db.get(
        OrganizationDocumentContent,
        first_document.document_id,
    )
    corrected_content = db.get(
        OrganizationDocumentContent,
        corrected_document.document_id,
    )

    assert original_content.content == FIRST_EVIDENCE
    assert corrected_content.content == CORRECTED_EVIDENCE