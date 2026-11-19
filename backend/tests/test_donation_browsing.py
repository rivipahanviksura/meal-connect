from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
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
from app.schemas.donation import DonationBrowseQuery
from app.services.donation_browse_service import browse_available_donations


NOW = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)


# SQLite test database එක සඳහා පමණක් JSONB support.
@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(element, compiler, **kwargs):
    return "JSON"


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    User.__table__.create(engine)
    Organization.__table__.create(engine)
    OrganizationMembership.__table__.create(engine)
    Donation.__table__.create(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def create_ngo_account(
    db,
    *,
    role=UserRole.ngo_staff,
    account_status=AccountStatus.active,
    organization_type=OrganizationType.ngo,
    verification_status=VerificationStatus.approved,
    member_status=MemberStatus.active,
    with_membership=True,
):
    user = User(
        user_id=1,
        first_name="Test",
        last_name="User",
        email="ngo@example.com",
        password_hash="test-only-placeholder",
        role=role,
        account_status=account_status,
    )

    organization = Organization(
        organization_id=1,
        name="Test NGO",
        type=organization_type,
        contact_email="organization@example.com",
        address_line="Test address",
        city="Kurunegala",
        verification_status=verification_status,
    )

    db.add_all([user, organization])
    db.flush()

    if with_membership:
        db.add(
            OrganizationMembership(
                membership_id=1,
                organization_id=1,
                user_id=1,
                membership_role=MembershipRole.owner,
                member_status=member_status,
            )
        )

    db.commit()


def create_donation(db, donation_id, **changes):
    # Donations belong to a separate Business account.
    if db.get(User, 2) is None:
        db.add(
            User(
                user_id=2,
                first_name="Business",
                last_name="Owner",
                email="business@example.com",
                password_hash="test-only-placeholder",
                role=UserRole.business_staff,
                account_status=AccountStatus.active,
            )
        )
        db.flush()

    if db.get(Organization, 2) is None:
        db.add(
            Organization(
                organization_id=2,
                name="Test Restaurant",
                type=OrganizationType.restaurant,
                contact_email="restaurant@example.com",
                address_line="Restaurant address",
                city="Colombo",
                verification_status=VerificationStatus.approved,
            )
        )
        db.flush()

        db.add(
            OrganizationMembership(
                membership_id=2,
                organization_id=2,
                user_id=2,
                membership_role=MembershipRole.owner,
                member_status=MemberStatus.active,
            )
        )
        db.flush()

    values = {
        "donation_id": donation_id,
        "organization_id": 2,
        "created_by_user_id": 2,
        "title": f"Donation {donation_id}",
        "category": "prepared_meal",
        "description": "Test food",
        "total_quantity": Decimal("10.00"),
        "allocated_quantity": Decimal("0.00"),
        "quantity_unit": "portions",
        "available_from": NOW - timedelta(hours=1),
        "pickup_deadline": NOW + timedelta(hours=1),
        "pickup_address": "Restaurant address",
        "pickup_city": "Colombo",
        "status": DonationStatus.available,
        "created_at": NOW - timedelta(hours=2),
    }

    values.update(changes)
    db.add(Donation(**values))
    db.commit()


def browse(db, **filters):
    return browse_available_donations(
        db,
        filters=DonationBrowseQuery(**filters),
        now=NOW,
    )


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(settings, "secret_key", SecretStr("meal29-test-only-nonproduction-secret"))
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: db)
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


def ngo_headers():
    return {"Authorization": f"Bearer {create_access_token(1)}"}


def test_browsing_requires_authentication(client):
    response = client.get("/api/v1/donations")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


@pytest.mark.parametrize("changes", [
    {"verification_status": VerificationStatus.pending},
    {"verification_status": VerificationStatus.suspended},
    {"account_status": AccountStatus.disabled},
    {"member_status": MemberStatus.invited},
    {"role": UserRole.business_staff, "organization_type": OrganizationType.restaurant},
    {"with_membership": False},
])
def test_unqualified_account_is_forbidden(db, client, changes):
    create_ngo_account(db, **changes)

    response = client.get("/api/v1/donations", headers=ngo_headers())

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize("params", [
    {"page": 2**63 + 2, "page_size": 1},
    {"sort": "wrong"},
    {"city": "   "},
    {"available_before": "2027-01-01T08:00:00"},
])
def test_invalid_browse_filters_return_validation_error(db, client, params):
    create_ngo_account(db)

    response = client.get("/api/v1/donations", headers=ngo_headers(), params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["fields"]


def test_verified_ngo_receives_paginated_list(db, client):
    create_ngo_account(db)
    now = datetime.now(timezone.utc)
    window = dict(available_from=now - timedelta(hours=1), pickup_deadline=now + timedelta(hours=1))
    create_donation(db, 1, **window)
    create_donation(db, 2, **window)

    response = client.get("/api/v1/donations", headers=ngo_headers(), params={
        "city": "COLOMBO", "category": "prepared_meal", "page": 2, "page_size": 1,
    })

    assert response.status_code == 200
    result = response.json()
    assert [item["donation_id"] for item in result["data"]] == [2]
    assert Decimal(result["data"][0]["remaining_quantity"]) == Decimal("10")
    assert result["pagination"] == dict(page=2, page_size=1, total_items=2, total_pages=2)


def test_available_donation_is_returned(db):
    create_ngo_account(db)
    create_donation(db, 1)

    result = browse(db)

    assert [item.donation_id for item in result.data] == [1]
    assert result.data[0].remaining_quantity == Decimal("10.00")
    assert result.pagination.total_items == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"status": DonationStatus.draft},
        {"status": DonationStatus.expired},
        {"status": DonationStatus.cancelled},
        {"status": DonationStatus.fully_allocated},
        {"status": DonationStatus.collected},
        {"pickup_deadline": NOW},
        {"pickup_deadline": NOW - timedelta(minutes=1)},
        {"available_from": NOW + timedelta(minutes=1)},
        {"allocated_quantity": Decimal("10.00")},
    ],
)
def test_unrequestable_donation_is_excluded(db, changes):
    create_ngo_account(db)
    create_donation(db, 1, **changes)

    result = browse(db)

    assert result.data == []
    assert result.pagination.total_items == 0


def test_remaining_quantity_filter(db):
    create_ngo_account(db)

    create_donation(
        db,
        1,
        status=DonationStatus.partially_allocated,
        allocated_quantity=Decimal("6.00"),
    )

    assert browse(db, min_quantity="5.00").data == []

    result = browse(db, min_quantity="4.00")

    assert [item.donation_id for item in result.data] == [1]
    assert result.data[0].remaining_quantity == Decimal("4.00")


def test_city_and_category_filters_ignore_case(db):
    create_ngo_account(db)
    create_donation(db, 1)

    result = browse(
        db,
        city=" colombo ",
        category="PREPARED_MEAL",
    )

    assert [item.donation_id for item in result.data] == [1]
    assert browse(db, city="Kandy").data == []


def test_pagination_and_deadline_sorting(db):
    create_ngo_account(db)

    for donation_id in range(1, 4):
        create_donation(
            db,
            donation_id,
            pickup_deadline=NOW + timedelta(hours=donation_id),
        )

    result = browse(
        db,
        sort="-pickup_deadline",
        page=2,
        page_size=2,
    )

    assert [item.donation_id for item in result.data] == [1]
    assert result.pagination.total_items == 3
    assert result.pagination.total_pages == 2


def test_ngo_can_browse_another_organizations_donation(db):
    create_ngo_account(db)
    create_donation(db, 1)

    result = browse(db)

    assert len(result.data) == 1
    assert result.data[0].organization_id == 2
    assert db.get(Organization, 1).type == OrganizationType.ngo
    assert db.get(Organization, 2).type == OrganizationType.restaurant


def test_suspended_publisher_is_excluded_from_data_and_count(db):
    create_donation(db, 1)
    assert browse(db).pagination.total_items == 1

    db.get(Organization, 2).verification_status = VerificationStatus.suspended
    db.commit()

    result = browse(db)
    assert result.data == []
    assert result.pagination.total_items == 0


def test_available_before_limits_listing_start(db):
    create_donation(db, 1, available_from=NOW - timedelta(hours=2))
    create_donation(db, 2, available_from=NOW)

    result = browse(db, available_before=NOW - timedelta(hours=1))

    assert [item.donation_id for item in result.data] == [1]


# MEAL-105: combined filter and pickup-deadline regression coverage.

def test_all_filters_use_intersection_for_items_and_pagination(db):
    # Both the selected rows meet *every* requested condition.
    matching = {
        "available_from": NOW - timedelta(hours=2),
        "pickup_deadline": NOW + timedelta(minutes=30),
        "allocated_quantity": Decimal("3.00"),
    }
    create_donation(db, 1, **matching)
    create_donation(db, 2, **{
        **matching,
        "pickup_deadline": NOW + timedelta(hours=1),  # Inclusive cutoff.
    })

    # Each other row violates exactly one (or more) filter constraints.
    create_donation(db, 3, **{**matching, "pickup_city": "Kandy"})
    create_donation(db, 4, **{**matching, "category": "vegetables"})
    create_donation(db, 5, **{**matching, "allocated_quantity": Decimal("8.00")})
    create_donation(db, 6, **{
        **matching,
        "pickup_deadline": NOW + timedelta(hours=1, seconds=1),
    })
    create_donation(db, 7, **{
        **matching,
        "available_from": NOW - timedelta(minutes=30),
    })
    create_donation(db, 8, **{
        **matching,
        "status": DonationStatus.partially_allocated,
    })
    create_donation(db, 9, **{**matching, "status": DonationStatus.draft})

    filters = {
        "city": " COLOMBO ",
        "category": "PREPARED_MEAL",
        "status": "available",
        "min_quantity": Decimal("5.00"),
        "available_before": NOW - timedelta(hours=1),
        "pickup_deadline_before": NOW + timedelta(hours=1),
        "page_size": 1,
    }

    first = browse(db, page=1, **filters)
    second = browse(db, page=2, **filters)
    empty = browse(db, page=3, **filters)

    assert [item.donation_id for item in first.data] == [1]
    assert [item.donation_id for item in second.data] == [2]
    assert empty.data == []
    assert first.pagination.total_items == 2
    assert second.pagination.total_items == 2
    assert empty.pagination.total_items == 2
    assert first.pagination.total_pages == 2
    assert second.data[0].remaining_quantity == Decimal("7.00")


def test_deadline_filter_is_independent_of_availability_start(db):
    create_donation(
        db,
        1,
        available_from=NOW - timedelta(hours=2),
        pickup_deadline=NOW + timedelta(hours=1),
    )
    create_donation(
        db,
        2,
        available_from=NOW - timedelta(minutes=30),
        pickup_deadline=NOW + timedelta(minutes=20),
    )

    # Filtering the pickup deadline includes #2, but filtering the start
    # timestamp includes #1. Existing available_before semantics must stay.
    deadline = browse(db, pickup_deadline_before=NOW + timedelta(minutes=30))
    start = browse(db, available_before=NOW - timedelta(hours=1))

    assert [item.donation_id for item in deadline.data] == [2]
    assert [item.donation_id for item in start.data] == [1]


def test_deadline_cutoff_uses_utc_instant_not_offset_wall_clock(db):
    create_donation(db, 1, pickup_deadline=NOW + timedelta(minutes=30))
    create_donation(db, 2, pickup_deadline=NOW + timedelta(minutes=31))

    colombo = timezone(timedelta(hours=5, minutes=30))
    local_cutoff = (NOW + timedelta(minutes=30)).astimezone(colombo)
    result = browse(db, pickup_deadline_before=local_cutoff)

    assert [item.donation_id for item in result.data] == [1]
    assert result.pagination.total_items == 1


def test_deadline_cutoff_cannot_resurrect_expired_or_unavailable_donations(db):
    create_donation(db, 1, pickup_deadline=NOW - timedelta(seconds=1))
    create_donation(db, 2, pickup_deadline=NOW)
    create_donation(db, 3, pickup_deadline=NOW + timedelta(minutes=10))
    create_donation(
        db,
        4,
        status=DonationStatus.cancelled,
        pickup_deadline=NOW + timedelta(minutes=10),
    )
    result = browse(db, pickup_deadline_before=NOW + timedelta(days=1))

    assert [item.donation_id for item in result.data] == [3]
    assert result.pagination.total_items == 1


def test_empty_filter_intersection_has_consistent_zero_count(db):
    create_donation(db, 1, pickup_city="Colombo")
    create_donation(db, 2, pickup_city="Kandy")

    result = browse(
        db,
        city="Colombo",
        category="prepared_meal",
        min_quantity=Decimal("5.00"),
        pickup_deadline_before=NOW + timedelta(minutes=1),
    )

    assert result.data == []
    assert result.pagination.total_items == 0
    assert result.pagination.total_pages == 0


@pytest.mark.parametrize(
    "invalid",
    [
        "2026-11-19T18:00:00",  # No timezone offset.
        "not-a-timestamp",
    ],
)
def test_deadline_filter_rejects_invalid_or_naive_timestamps(invalid):
    with pytest.raises(ValidationError):
        DonationBrowseQuery(pickup_deadline_before=invalid)


def test_deadline_filter_can_be_used_without_any_other_filter():
    filters = DonationBrowseQuery(
        pickup_deadline_before="2026-11-19T18:00:00+05:30"
    )

    assert filters.city is None
    assert filters.available_before is None
    assert filters.pickup_deadline_before.utcoffset() == timedelta(
        hours=5, minutes=30
    )


def test_authenticated_ngo_can_combine_filters_over_http(db, client):
    create_ngo_account(db)
    current = datetime.now(timezone.utc)
    create_donation(
        db,
        1,
        available_from=current - timedelta(hours=2),
        pickup_deadline=current + timedelta(minutes=15),
    )
    create_donation(
        db,
        2,
        available_from=current - timedelta(hours=2),
        pickup_deadline=current + timedelta(hours=2),
    )

    response = client.get(
        "/api/v1/donations",
        headers=ngo_headers(),
        params={
            "city": "Colombo",
            "category": "prepared_meal",
            "min_quantity": "5.00",
            "pickup_deadline_before": (
                current + timedelta(minutes=30)
            ).isoformat(),
        },
    )

    assert response.status_code == 200
    assert [item["donation_id"] for item in response.json()["data"]] == [1]
    assert response.json()["pagination"]["total_items"] == 1


def test_http_rejects_naive_deadline_without_leaking_listings(db, client):
    create_ngo_account(db)
    response = client.get(
        "/api/v1/donations",
        headers=ngo_headers(),
        params={"pickup_deadline_before": "2026-11-19T18:00:00"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["fields"]


def test_existing_authorization_still_blocks_anonymous_deadline_queries(client):
    response = client.get(
        "/api/v1/donations",
        params={"pickup_deadline_before": "2026-11-19T18:00:00Z"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_available_before_matches_instant_across_timezone_offsets(db):
    create_donation(db, 1, available_from=NOW - timedelta(hours=2))
    create_donation(db, 2, available_from=NOW - timedelta(minutes=10))

    cutoff_utc = NOW - timedelta(hours=1)
    cutoff_colombo = cutoff_utc.astimezone(
        timezone(timedelta(hours=5, minutes=30))
    )

    utc_result = browse(db, available_before=cutoff_utc)
    colombo_result = browse(db, available_before=cutoff_colombo)

    assert [item.donation_id for item in utc_result.data] == [1]
    assert [item.donation_id for item in colombo_result.data] == [1]


def test_discovery_now_matches_instant_across_timezone_offsets(db):
    create_donation(
        db,
        1,
        available_from=NOW - timedelta(hours=1),
        pickup_deadline=NOW + timedelta(hours=1),
    )
    now_colombo = NOW.astimezone(
        timezone(timedelta(hours=5, minutes=30))
    )

    utc_result = browse_available_donations(
        db, filters=DonationBrowseQuery(), now=NOW
    )
    local_result = browse_available_donations(
        db, filters=DonationBrowseQuery(), now=now_colombo
    )

    assert [item.donation_id for item in utc_result.data] == [1]
    assert [item.donation_id for item in local_result.data] == [1]
