
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.organization import (
    MemberStatus,
    MembershipRole,
    Organization,
    OrganizationMembership,
    OrganizationType,
    VerificationStatus,
)
from app.db.models.user import AccountStatus, User, UserRole
from app.schemas.organization_application import (
    BusinessApplication,
    NgoApplication,
    NgoOperationalDetails,
)
from app.services.organization_application import (
    ApplicantNotAllowedError,
    ApplicationAlreadyExistsError,
    RegistrationNumberAlreadyExistsError,
    create_application_draft,
)


@compiles(BigInteger, "sqlite")
def compile_bigint_sqlite(type_, compiler, **kwargs):
    return "INTEGER"


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kwargs):
    return "JSON"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Organization.__table__,
            OrganizationMembership.__table__,
        ],
    )

    with Session(engine) as session:
        yield session

    engine.dispose()


@pytest.fixture
def business_user(db):
    user = User(
        first_name="Business",
        last_name="Applicant",
        email="business@example.com",
        password_hash="test-hash",
        role=UserRole.business_staff,
        account_status=AccountStatus.active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def ngo_user(db):
    user = User(
        first_name="NGO",
        last_name="Applicant",
        email="ngo@example.com",
        password_hash="test-hash",
        role=UserRole.ngo_staff,
        account_status=AccountStatus.active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def business_payload(
    registration_number="BR-1001",
    contact_email="contact@business.example",
):
    return BusinessApplication(
        organization_type="business",
        business_subtype="restaurant",
        name="Test Restaurant",
        registration_number=registration_number,
        contact_email=contact_email,
        contact_phone="+94112345678",
        address_line="123 Main Street",
        city="Colombo",
        district="Colombo",
        representative_name="Test Representative",
        representative_designation="Owner",
        pickup_location="123 Main Street, Colombo",
    )


def ngo_payload():
    return NgoApplication(
        organization_type="ngo",
        name="Test NGO",
        registration_number="NGO-1001",
        contact_email="contact@ngo.example",
        contact_phone="+94112345678",
        address_line="45 Charity Road",
        city="Colombo",
        district="Colombo",
        representative_name="NGO Representative",
        representative_designation="Director",
        registration_authority="NGO Secretariat",
        registration_date=date(2020, 1, 1),
        operational_details=NgoOperationalDetails(
            operating_area="Colombo",
            distribution_area="Western Province",
            operational_capability="Food distribution",
        ),
    )


def test_business_application_is_created(db, business_user):
    result = create_application_draft(
        db,
        business_user.user_id,
        business_payload(),
    )

    organization = db.get(
        Organization,
        result.organization_id,
    )

    membership = (
        db.query(OrganizationMembership)
        .filter_by(
            organization_id=result.organization_id,
            user_id=business_user.user_id,
        )
        .one()
    )

    assert organization is not None
    assert organization.name == "Test Restaurant"
    assert organization.type == OrganizationType.restaurant
    assert organization.verification_status == VerificationStatus.pending

    assert membership.membership_role == MembershipRole.owner
    assert membership.member_status == MemberStatus.invited


def test_ngo_application_is_created(db, ngo_user):
    result = create_application_draft(
        db,
        ngo_user.user_id,
        ngo_payload(),
    )

    organization = db.get(
        Organization,
        result.organization_id,
    )

    assert organization is not None
    assert organization.name == "Test NGO"
    assert organization.type == OrganizationType.ngo
    assert organization.verification_status == VerificationStatus.pending


def test_business_user_cannot_create_ngo_application(
    db,
    business_user,
):
    with pytest.raises(ApplicantNotAllowedError):
        create_application_draft(
            db,
            business_user.user_id,
            ngo_payload(),
        )

    assert db.query(Organization).count() == 0


def test_ngo_user_cannot_create_business_application(
    db,
    ngo_user,
):
    with pytest.raises(ApplicantNotAllowedError):
        create_application_draft(
            db,
            ngo_user.user_id,
            business_payload(),
        )

    assert db.query(Organization).count() == 0


def test_suspended_user_cannot_create_application(
    db,
    business_user,
):
    business_user.account_status = AccountStatus.suspended
    db.commit()

    with pytest.raises(ApplicantNotAllowedError):
        create_application_draft(
            db,
            business_user.user_id,
            business_payload(),
        )

    assert db.query(Organization).count() == 0


def test_user_cannot_create_second_application(
    db,
    business_user,
):
    create_application_draft(
        db,
        business_user.user_id,
        business_payload(),
    )

    with pytest.raises(ApplicationAlreadyExistsError):
        create_application_draft(
            db,
            business_user.user_id,
            business_payload(
                registration_number="BR-2002",
                contact_email="another@business.example",
            ),
        )

    assert db.query(Organization).count() == 1


def test_duplicate_registration_number_is_rejected(
    db,
    business_user,
    monkeypatch,
):
    second_user = User(
        first_name="Second",
        last_name="Applicant",
        email="second@example.com",
        password_hash="test-hash",
        role=UserRole.business_staff,
        account_status=AccountStatus.active,
    )
    db.add(second_user)
    db.commit()

    create_application_draft(
        db,
        business_user.user_id,
        business_payload(),
    )

    postgres_error = SimpleNamespace(
        diag=SimpleNamespace(
            constraint_name="uq_organizations_registration_identity"
        )
    )

    def raise_postgres_integrity_error():
        raise IntegrityError(
            "INSERT INTO organizations",
            {},
            postgres_error,
        )

    monkeypatch.setattr(
        db,
        "commit",
        raise_postgres_integrity_error,
    )

    with pytest.raises(RegistrationNumberAlreadyExistsError):
        create_application_draft(
            db,
            second_user.user_id,
            business_payload(),
        )

    assert db.query(Organization).count() == 1
