from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy import BigInteger

from app.db.base import Base
from app.db.models.user import User, UserRole
from app.db.models.organization import (
    Organization,
    OrganizationType,
    VerificationStatus,
)
from app.db.models.donation import Donation, DonationStatus
from app.schemas.donation import DonationCreate
from app.services.donation_service import create_donation


@compiles(BigInteger, "sqlite")
def compile_big_integer(element, compiler, **kwargs):
    return "INTEGER"


@compiles(JSONB, "sqlite")
def compile_jsonb(element, compiler, **kwargs):
    return "JSON"


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Organization.__table__,
            Donation.__table__,
        ],
    )

    with Session(engine) as session:
        yield session

    engine.dispose()


def create_test_user(db):
    user = User(
        first_name="Test",
        last_name="Business",
        email="business@example.com",
        password_hash="test-password-hash",
        role=UserRole.business_staff,
    )

    db.add(user)
    db.flush()

    return user


def create_test_organization(db, user):
    organization = Organization(
        name="Test Restaurant",
        type=OrganizationType.restaurant,
        contact_email="restaurant@example.com",
        address_line="Main Street",
        city="Colombo",
        verification_status=VerificationStatus.approved,
        verified_by_user_id=user.user_id,
    )

    db.add(organization)
    db.flush()

    return organization


def valid_donation_data():
    return DonationCreate(
        title="Fresh Vegetables",
        category="Vegetables",
        description="Fresh surplus vegetables",
        total_quantity=Decimal("25.50"),
        quantity_unit="kg",
        allergen_info=None,
        storage_instructions="Keep refrigerated",
        prepared_at=None,
        available_from="2026-11-15T09:00:00+05:30",
        pickup_deadline="2026-11-15T17:00:00+05:30",
        pickup_address="Main Street",
        pickup_city="Colombo",
    )


def test_donation_is_saved_and_linked_to_organization(db_session):
    user = create_test_user(db_session)
    organization = create_test_organization(db_session, user)

    donation_data = valid_donation_data()

    created_donation = create_donation(
        db=db_session,
        donation_data=donation_data,
        organization=organization,
        current_user=user,
    )

    saved_donation = db_session.scalar(
        select(Donation).where(
            Donation.donation_id == created_donation.donation_id
        )
    )

    assert saved_donation is not None
    assert saved_donation.organization_id == organization.organization_id
    assert saved_donation.created_by_user_id == user.user_id


def test_donation_has_initial_status_and_creation_timestamp(db_session):
    user = create_test_user(db_session)
    organization = create_test_organization(db_session, user)

    created_donation = create_donation(
        db=db_session,
        donation_data=valid_donation_data(),
        organization=organization,
        current_user=user,
    )

    saved_donation = db_session.scalar(
        select(Donation).where(
            Donation.donation_id == created_donation.donation_id
        )
    )

    assert saved_donation.status == DonationStatus.draft
    assert saved_donation.created_at is not None
    assert saved_donation.allocated_quantity == Decimal("0.00")
