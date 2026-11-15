from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy import BigInteger

from app.db.base import Base
from app.db.models.user import User
from app.db.models.organization import Organization, OrganizationType, VerificationStatus
from app.db.models.donation import Donation, DonationStatus
from app.services.donation_service import browse_available_donations


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


@pytest.fixture
def donation_owner(db_session):
    user = User(
        first_name="Test",
        last_name="Business",
        email="business@example.com",
        password_hash="test-password-hash",
        role="business_staff",
    )
    db_session.add(user)
    db_session.flush()

    organization = Organization(
        name="Test Restaurant",
        type=OrganizationType.restaurant,
        contact_email="restaurant@example.com",
        address_line="Main Street",
        city="Colombo",
        verification_status=VerificationStatus.approved,
        verified_by_user_id=user.user_id,
    )
    db_session.add(organization)
    db_session.flush()

    return user, organization


def create_donation(
    db,
    owner,
    title,
    status=DonationStatus.available,
    available_from=datetime(2026, 11, 15, 9, 0),
    pickup_deadline=datetime(2026, 11, 15, 17, 0),
    total_quantity=Decimal("25.00"),
    allocated_quantity=Decimal("0.00"),
):
    user, organization = owner

    donation = Donation(
        organization_id=organization.organization_id,
        created_by_user_id=user.user_id,
        title=title,
        category="Vegetables",
        description="Fresh surplus vegetables",
        total_quantity=total_quantity,
        allocated_quantity=allocated_quantity,
        quantity_unit="kg",
        available_from=available_from,
        pickup_deadline=pickup_deadline,
        pickup_address="Main Street",
        pickup_city="Colombo",
        status=status,
    )

    db.add(donation)
    db.flush()

    return donation


TEST_NOW = datetime(2026, 11, 15, 12, 0)


def test_browse_returns_available_donations(db_session, donation_owner):
    create_donation(
        db_session,
        donation_owner,
        "Available vegetables",
        status=DonationStatus.available,
    )

    results = browse_available_donations(
        db_session,
        current_time=TEST_NOW,
    )

    assert len(results) == 1
    assert results[0].title == "Available vegetables"


def test_browse_returns_partially_allocated_donations(
    db_session,
    donation_owner,
):
    create_donation(
        db_session,
        donation_owner,
        "Partially allocated vegetables",
        status=DonationStatus.partially_allocated,
        total_quantity=Decimal("25.00"),
        allocated_quantity=Decimal("10.00"),
    )

    results = browse_available_donations(
        db_session,
        current_time=TEST_NOW,
    )

    assert len(results) == 1
    assert results[0].allocated_quantity == Decimal("10.00")


@pytest.mark.parametrize(
    "status",
    [
        DonationStatus.draft,
        DonationStatus.fully_allocated,
        DonationStatus.collected,
        DonationStatus.expired,
        DonationStatus.cancelled,
    ],
)
def test_browse_excludes_unavailable_statuses(
    db_session,
    donation_owner,
    status,
):
    create_donation(
        db_session,
        donation_owner,
        f"{status.value} donation",
        status=status,
    )

    results = browse_available_donations(
        db_session,
        current_time=TEST_NOW,
    )

    assert results == []


def test_browse_excludes_donations_not_yet_available(
    db_session,
    donation_owner,
):
    create_donation(
        db_session,
        donation_owner,
        "Future donation",
        available_from=datetime(2026, 11, 15, 13, 0),
    )

    results = browse_available_donations(
        db_session,
        current_time=TEST_NOW,
    )

    assert results == []


def test_browse_excludes_expired_deadlines(
    db_session,
    donation_owner,
):
    create_donation(
        db_session,
        donation_owner,
        "Expired deadline",
        pickup_deadline=datetime(2026, 11, 15, 11, 59),
    )

    results = browse_available_donations(
        db_session,
        current_time=TEST_NOW,
    )

    assert results == []


def test_browse_excludes_fully_allocated_quantity(
    db_session,
    donation_owner,
):
    create_donation(
        db_session,
        donation_owner,
        "No remaining quantity",
        total_quantity=Decimal("25.00"),
        allocated_quantity=Decimal("25.00"),
    )

    results = browse_available_donations(
        db_session,
        current_time=TEST_NOW,
    )

    assert results == []


def test_browse_returns_only_donations_with_remaining_quantity(
    db_session,
    donation_owner,
):
    create_donation(
        db_session,
        donation_owner,
        "Available donation",
        total_quantity=Decimal("25.00"),
        allocated_quantity=Decimal("5.00"),
    )

    create_donation(
        db_session,
        donation_owner,
        "Fully allocated donation",
        total_quantity=Decimal("25.00"),
        allocated_quantity=Decimal("25.00"),
    )

    results = browse_available_donations(
        db_session,
        current_time=TEST_NOW,
    )

    assert len(results) == 1
    assert results[0].title == "Available donation"


def test_browse_orders_by_pickup_deadline(
    db_session,
    donation_owner,
):
    create_donation(
        db_session,
        donation_owner,
        "Later deadline",
        pickup_deadline=datetime(2026, 11, 15, 18, 0),
    )

    create_donation(
        db_session,
        donation_owner,
        "Earlier deadline",
        pickup_deadline=datetime(2026, 11, 15, 14, 0),
    )

    results = browse_available_donations(
        db_session,
        current_time=TEST_NOW,
    )

    assert [item.title for item in results] == [
        "Earlier deadline",
        "Later deadline",
    ]


def test_verified_ngo_can_browse_donations(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.dependencies import (
        get_active_user,
        get_current_organization,
    )
    from app.api.donations import router
    from app.db.session import get_db
    from app.db.models.user import UserRole

    user = SimpleNamespace(
        user_id=10,
        role=UserRole.ngo_staff,
    )
    organization = SimpleNamespace(
        organization_id=20,
    )

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_active_user] = lambda: user
    app.dependency_overrides[get_current_organization] = (
        lambda: organization
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()

    client = TestClient(app)
    mock_browse = MagicMock(return_value=[])

    monkeypatch.setattr(
        "app.api.donations.browse_available_donations",
        mock_browse,
    )

    response = client.get("/donations/")

    assert response.status_code == 200
    assert response.json() == []
    mock_browse.assert_called_once()


def test_unverified_ngo_cannot_browse_donations(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from app.api.dependencies import (
        get_active_user,
        get_current_organization,
    )
    from app.api.donations import router
    from app.db.session import get_db
    from app.db.models.user import UserRole

    user = SimpleNamespace(
        user_id=11,
        role=UserRole.ngo_staff,
    )

    def reject_unverified_organization():
        raise HTTPException(
            status_code=403,
            detail="Organization is not approved.",
        )

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_active_user] = lambda: user
    app.dependency_overrides[get_current_organization] = (
        reject_unverified_organization
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()

    client = TestClient(app)
    mock_browse = MagicMock(return_value=[])

    monkeypatch.setattr(
        "app.api.donations.browse_available_donations",
        mock_browse,
    )

    response = client.get("/donations/")

    assert response.status_code == 403
    mock_browse.assert_not_called()


def test_business_user_cannot_browse_donations(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.dependencies import (
        get_active_user,
        get_current_organization,
    )
    from app.api.donations import router
    from app.core.exception_handlers import APIException
    from app.db.session import get_db
    from app.db.models.user import UserRole

    user = SimpleNamespace(
        user_id=12,
        role=UserRole.business_staff,
    )
    organization = SimpleNamespace(
        organization_id=30,
    )

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_active_user] = lambda: user
    app.dependency_overrides[get_current_organization] = (
        lambda: organization
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()

    client = TestClient(app)
    mock_browse = MagicMock(return_value=[])

    monkeypatch.setattr(
        "app.api.donations.browse_available_donations",
        mock_browse,
    )

    with pytest.raises(APIException) as exc_info:
        client.get("/donations/")

    assert exc_info.value.status_code == 403
    mock_browse.assert_not_called()
