"""MEAL-101: regression coverage for the existing verified-NGO listing API.

This task intentionally reuses the implementation merged by PR #29.  It does
not introduce another endpoint, change approved filter names, or alter models.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models.donation import Donation, DonationStatus
from app.db.models.organization import (
    MemberStatus,
    MembershipRole,
    Organization,
    OrganizationMembership,
    OrganizationType,
    VerificationStatus,
)
from app.db.models.user import AccountStatus, User, UserRole
from app.db.session import get_db
from app.main import app
from app.schemas.donation import DonationBrowseQuery
from app.services.donation_availability import is_donation_requestable
from app.services.donation_browse_service import browse_available_donations


NOW = datetime(2026, 11, 18, 10, tzinfo=timezone.utc)


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_test(element, compiler, **kw):
    """Adapt PostgreSQL JSONB for SQLite-only unit tests, not production."""
    return "JSON"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (User, Organization, OrganizationMembership, Donation):
        model.__table__.create(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def _add_ngo(db: Session, verification=VerificationStatus.approved):
    db.add(
        User(
            user_id=1,
            first_name="NGO",
            last_name="Owner",
            email="ngo101@example.test",
            password_hash="disabled-test-hash",
            role=UserRole.ngo_staff,
            account_status=AccountStatus.active,
        )
    )
    db.add(
        Organization(
            organization_id=1,
            name="NGO 101",
            type=OrganizationType.ngo,
            contact_email="ngo101@example.test",
            address_line="Test Street",
            city="Kandy",
            verification_status=verification,
        )
    )
    db.flush()
    db.add(
        OrganizationMembership(
            membership_id=1,
            organization_id=1,
            user_id=1,
            membership_role=MembershipRole.owner,
            member_status=MemberStatus.active,
        )
    )
    db.commit()


def _publisher(
    db: Session,
    organization_id: int = 2,
    *,
    status=VerificationStatus.approved,
    kind=OrganizationType.restaurant,
):
    db.add(
        User(
            user_id=organization_id,
            first_name="Publisher",
            last_name="Test",
            email=f"publisher{organization_id}@example.test",
            password_hash="disabled-test-hash",
            role=UserRole.business_staff,
            account_status=AccountStatus.active,
        )
    )
    db.add(
        Organization(
            organization_id=organization_id,
            name=f"Publisher {organization_id}",
            type=kind,
            contact_email=f"publisher{organization_id}@example.test",
            address_line="Test Road",
            city="Colombo",
            verification_status=status,
        )
    )
    db.commit()


def _donation(db: Session, donation_id: int, organization_id: int = 2, **overrides):
    values = dict(
        donation_id=donation_id,
        organization_id=organization_id,
        created_by_user_id=organization_id,
        title=f"Food listing {donation_id}",
        category="prepared_meal",
        total_quantity=Decimal("10.00"),
        allocated_quantity=Decimal("0.00"),
        quantity_unit="portions",
        available_from=NOW - timedelta(hours=2),
        pickup_deadline=NOW + timedelta(hours=2),
        pickup_address="Collection Road",
        pickup_city="Colombo",
        status=DonationStatus.available,
        created_at=NOW - timedelta(hours=3),
    )
    values.update(overrides)
    item = Donation(**values)
    db.add(item)
    db.commit()
    return item


def _browse(db: Session, **params):
    return browse_available_donations(db, filters=DonationBrowseQuery(**params), now=NOW)


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(
        settings, "secret_key", SecretStr("MEAL101-test-only-secret-not-for-production")
    )
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def _auth_header():
    return {"Authorization": f"Bearer {create_access_token(1)}"}


def test_only_requestable_donations_appear_in_data_and_total(db):
    _publisher(db)
    _donation(db, 10)
    _donation(db, 11, status=DonationStatus.partially_allocated,
              allocated_quantity=Decimal("6.00"))
    _donation(db, 12, status=DonationStatus.draft)
    _donation(db, 13, status=DonationStatus.expired)
    _donation(db, 14, status=DonationStatus.cancelled)
    _donation(db, 15, status=DonationStatus.collected)
    _donation(db, 16, status=DonationStatus.fully_allocated,
              allocated_quantity=Decimal("10.00"))
    _donation(db, 17, allocated_quantity=Decimal("10.00"))
    _donation(db, 18, available_from=NOW + timedelta(seconds=1))
    _donation(db, 19, pickup_deadline=NOW)
    _donation(db, 20, available_from=NOW)

    result = _browse(db)
    assert [item.donation_id for item in result.data] == [10, 11, 20]
    assert result.pagination.total_items == 3
    assert result.pagination.total_pages == 1
    assert result.data[1].remaining_quantity == Decimal("4.00")


@pytest.mark.parametrize("verification", [
    VerificationStatus.pending,
    VerificationStatus.rejected,
    VerificationStatus.suspended,
])
def test_unverified_publishers_excluded_from_items_and_counts(db, verification):
    _publisher(db, organization_id=2)
    _publisher(db, organization_id=3, status=verification)
    _donation(db, 10, organization_id=2)
    _donation(db, 11, organization_id=3)

    result = _browse(db)
    assert [item.donation_id for item in result.data] == [10]
    assert result.pagination.total_items == 1


def test_approved_bakeries_included_but_ngo_publishers_excluded(db):
    _publisher(db, organization_id=2, kind=OrganizationType.bakery)
    _publisher(db, organization_id=3, kind=OrganizationType.ngo)
    _donation(db, 10, organization_id=2)
    _donation(db, 11, organization_id=3)

    result = _browse(db)
    assert [item.donation_id for item in result.data] == [10]
    assert result.pagination.total_items == 1


def test_pagination_ignores_unavailable_rows_and_is_deterministic(db):
    _publisher(db)
    for i in range(10, 15):
        _donation(db, i)
    _donation(db, 15, status=DonationStatus.cancelled)

    first = _browse(db, page=1, page_size=2)
    second = _browse(db, page=2, page_size=2)
    third = _browse(db, page=3, page_size=2)
    assert [[d.donation_id for d in p.data] for p in (first, second, third)] == [
        [10, 11], [12, 13], [14]
    ]
    assert all(p.pagination.total_items == 5 for p in (first, second, third))
    assert all(p.pagination.total_pages == 3 for p in (first, second, third))


def test_meal110_python_requestability_matches_sql_discovery(db):
    _publisher(db)
    candidates = [
        _donation(db, 10, available_from=NOW),
        _donation(db, 11, available_from=NOW + timedelta(microseconds=1)),
        _donation(db, 12, pickup_deadline=NOW),
        _donation(db, 13, pickup_deadline=NOW + timedelta(microseconds=1)),
        _donation(db, 14, status=DonationStatus.partially_allocated,
                  allocated_quantity=Decimal("9.00")),
        _donation(db, 15, status=DonationStatus.draft),
    ]
    # SQLite does not preserve TIMESTAMPTZ offsets. Reattach UTC only in this
    # test adapter, without modifying mapped/persisted rows. PostgreSQL stores
    # timezone-aware instants and does not need this adaptation.
    def requestable_in_test_db(donation):
        utc_donation = SimpleNamespace(
            status=donation.status,
            available_from=donation.available_from.replace(tzinfo=timezone.utc),
            pickup_deadline=donation.pickup_deadline.replace(tzinfo=timezone.utc),
            total_quantity=donation.total_quantity,
            allocated_quantity=donation.allocated_quantity,
        )
        return is_donation_requestable(utc_donation, now=NOW)

    expected_ids = {
        d.donation_id for d in candidates if requestable_in_test_db(d)
    }
    actual_ids = {item.donation_id for item in _browse(db).data}
    assert actual_ids == expected_ids


def test_http_api_enforces_verified_ngo_and_keeps_response_envelope(db, client):
    _add_ngo(db)
    _publisher(db)
    current = datetime.now(timezone.utc)
    _donation(
        db, 10,
        available_from=current - timedelta(hours=1),
        pickup_deadline=current + timedelta(hours=1),
    )
    _donation(
        db, 11,
        status=DonationStatus.expired,
        available_from=current - timedelta(hours=2),
        pickup_deadline=current - timedelta(hours=1),
    )

    assert client.get("/api/v1/donations").status_code == 401

    response = client.get("/api/v1/donations", headers=_auth_header())
    assert response.status_code == 200
    assert [item["donation_id"] for item in response.json()["data"]] == [10]
    assert response.json()["pagination"] == {
        "page": 1, "page_size": 20, "total_items": 1, "total_pages": 1
    }
    assert Decimal(response.json()["data"][0]["remaining_quantity"]) == 10

    db.get(Organization, 1).verification_status = VerificationStatus.suspended
    db.commit()
    forbidden = client.get("/api/v1/donations", headers=_auth_header())
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"
