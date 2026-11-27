from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import app.services.donation_browse_service as browse_service

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
from app.db.session import get_db, get_engine
from app.main import app


NOW = datetime(2035, 1, 15, 10, 0, tzinfo=timezone.utc)


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return NOW.replace(tzinfo=None)
        return NOW.astimezone(tz)


@pytest.fixture
def context(monkeypatch):
    assert settings.database_url is not None
    url = make_url(settings.database_url.get_secret_value())

    assert url.get_backend_name() == "postgresql"
    assert url.database == "meal_connect_test"
    assert url.host in {"localhost", "127.0.0.1", "::1"}

    monkeypatch.setattr(
        settings,
        "secret_key",
        SecretStr("meal106-local-test-signing-key-0123456789abcdef"),
    )
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(browse_service, "datetime", FrozenDateTime)

    previous = app.dependency_overrides.copy()
    engine = get_engine()

    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT current_database()")
            ).scalar_one() == "meal_connect_test"

            connection.rollback()
            outer = connection.begin()

            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    unique = uuid4().hex

                    def account(suffix, kind, role, verification):
                        user = User(
                            first_name="MEAL106",
                            last_name="QA",
                            email=f"meal106-{unique}-{suffix}@example.com",
                            password_hash="fixture-only-no-password-login",
                            role=role,
                            account_status=AccountStatus.active,
                        )
                        organization = Organization(
                            name=f"MEAL106 {suffix} {unique}",
                            type=kind,
                            contact_email=user.email,
                            address_line="QA Test Road",
                            city="Kurunegala",
                            verification_status=verification,
                        )
                        db.add_all([user, organization])
                        db.flush()

                        db.add(
                            OrganizationMembership(
                                organization_id=organization.organization_id,
                                user_id=user.user_id,
                                membership_role=MembershipRole.owner,
                                member_status=MemberStatus.active,
                            )
                        )
                        db.flush()
                        return user, organization

                    ngo_user, _ = account(
                        "ngo",
                        OrganizationType.ngo,
                        UserRole.ngo_staff,
                        VerificationStatus.approved,
                    )
                    donor_user, donor = account(
                        "donor",
                        OrganizationType.restaurant,
                        UserRole.business_staff,
                        VerificationStatus.approved,
                    )
                    pending_user, pending_org = account(
                        "pending",
                        OrganizationType.restaurant,
                        UserRole.business_staff,
                        VerificationStatus.pending,
                    )

                    city_a = f"QA-A-{unique}"
                    city_b = f"QA-B-{unique}"
                    category_a = f"qa_food_a_{unique}"
                    category_b = f"qa_food_b_{unique}"

                    def donation(
                        name,
                        city,
                        category,
                        start,
                        *,
                        allocated="0",
                        total="10",
                        status=DonationStatus.available,
                        deadline=None,
                        publisher=None,
                        creator=None,
                    ):
                        item = Donation(
                            organization_id=(
                                publisher.organization_id
                                if publisher is not None
                                else donor.organization_id
                            ),
                            created_by_user_id=(
                                creator.user_id
                                if creator is not None
                                else donor_user.user_id
                            ),
                            title=f"MEAL106 {name} {unique}",
                            category=category,
                            total_quantity=Decimal(total),
                            allocated_quantity=Decimal(allocated),
                            quantity_unit="portions",
                            available_from=start,
                            pickup_deadline=(
                                deadline
                                if deadline is not None
                                else NOW + timedelta(hours=1)
                            ),
                            pickup_address="QA Road",
                            pickup_city=city,
                            status=status,
                        )
                        db.add(item)
                        db.flush()
                        return item.donation_id

                    ids = {
                        "a": donation(
                            "A",
                            city_a,
                            category_a,
                            NOW - timedelta(hours=2),
                            allocated="6",
                            status=DonationStatus.partially_allocated,
                        ),
                        "b": donation(
                            "B",
                            city_a,
                            category_b,
                            NOW - timedelta(hours=1),
                            allocated="4",
                            status=DonationStatus.partially_allocated,
                            deadline=NOW + timedelta(hours=2),
                        ),
                        "c": donation(
                            "C",
                            city_b,
                            category_a,
                            NOW,
                            deadline=NOW + timedelta(hours=3),
                        ),
                        "d": donation(
                            "D",
                            city_b,
                            category_b,
                            NOW - timedelta(minutes=30),
                            total="0.01",
                            deadline=NOW + timedelta(hours=4),
                        ),
                    }

                    hidden = {
                        donation(
                            "deadline-due",
                            city_a,
                            category_a,
                            NOW - timedelta(hours=1),
                            deadline=NOW,
                        ),
                        donation(
                            "future-start",
                            city_a,
                            category_a,
                            NOW + timedelta(microseconds=1),
                        ),
                        donation(
                            "no-stock",
                            city_a,
                            category_a,
                            NOW - timedelta(hours=1),
                            allocated="10",
                        ),
                        donation(
                            "cancelled",
                            city_a,
                            category_a,
                            NOW - timedelta(hours=1),
                            status=DonationStatus.cancelled,
                        ),
                        donation(
                            "unapproved-publisher",
                            city_a,
                            category_a,
                            NOW - timedelta(hours=1),
                            publisher=pending_org,
                            creator=pending_user,
                        ),
                    }

                    user_id = ngo_user.user_id
                    db.commit()

                    def override_db():
                        yield db

                    app.dependency_overrides[get_db] = override_db

                    with TestClient(app) as client:
                        yield SimpleNamespace(
                            client=client,
                            headers={
                                "Authorization": (
                                    f"Bearer {create_access_token(user_id)}"
                                )
                            },
                            ids=ids,
                            hidden=hidden,
                            city_a=city_a,
                            city_b=city_b,
                            category_a=category_a,
                            category_b=category_b,
                        )
            finally:
                outer.rollback()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()


def get_page(context, **params):
    response = context.client.get(
        "/api/v1/donations",
        params=params,
        headers=context.headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body["data"], list)
    assert isinstance(body["pagination"], dict)
    return body


def assert_matches(context, body, names):
    expected = {context.ids[name] for name in names}
    actual = {item["donation_id"] for item in body["data"]}

    assert actual == expected
    assert body["pagination"]["total_items"] == len(expected)
    assert body["pagination"]["total_pages"] == (1 if expected else 0)


@pytest.mark.parametrize(
    "city,category,quantity,cutoff_hours,expected",
    [
        ("a", "a", "4", -2, ["a"]),
        ("a", "a", "4.01", -2, []),
        ("a", "b", "6", -1, ["b"]),
        ("b", "a", "10", 0, ["c"]),
    ],
)
def test_combined_filters_use_and_semantics(
    context, city, category, quantity, cutoff_hours, expected
):
    body = get_page(
        context,
        city=getattr(context, f"city_{city}").upper(),
        category=getattr(context, f"category_{category}").upper(),
        min_quantity=quantity,
        available_before=(
            NOW + timedelta(hours=cutoff_hours)
        ).isoformat(),
    )
    assert_matches(context, body, expected)


@pytest.mark.parametrize(
    "minimum,expected",
    [
        ("3.99", ["a", "b"]),
        ("4.00", ["a", "b"]),
        ("4.01", ["b"]),
        ("6.00", ["b"]),
        ("6.01", []),
    ],
)
def test_min_quantity_uses_remaining_stock_inclusively(
    context, minimum, expected
):
    body = get_page(
        context,
        city=context.city_a,
        min_quantity=minimum,
    )
    assert_matches(context, body, expected)

    for item in body["data"]:
        assert Decimal(item["remaining_quantity"]) >= Decimal(minimum)


@pytest.mark.parametrize(
    "microseconds,local_offset,expected",
    [
        (-1, False, []),
        (0, False, ["a"]),
        (1, False, ["a"]),
        (0, True, ["a"]),
        (3_600_000_000, False, ["a", "b"]),
    ],
)
def test_available_before_boundary_and_timezone(
    context, microseconds, local_offset, expected
):
    cutoff = NOW - timedelta(hours=2)
    cutoff += timedelta(microseconds=microseconds)

    if local_offset:
        cutoff = cutoff.astimezone(
            timezone(timedelta(hours=5, minutes=30))
        )

    body = get_page(
        context,
        city=context.city_a,
        available_before=cutoff.isoformat(),
    )
    assert_matches(context, body, expected)


def test_empty_result_has_zero_counts(context):
    body = get_page(
        context,
        city=f"no-such-city-{uuid4().hex}",
    )
    assert_matches(context, body, [])


def all_eligible(context):
    """Read every page; do not assume the test database is empty."""
    result = []
    page = 1

    while True:
        body = get_page(context, page=page, page_size=100)
        result.extend(body["data"])

        if page >= body["pagination"]["total_pages"]:
            assert len(result) == body["pagination"]["total_items"]
            return result

        page += 1


def test_removing_filters_restores_eligible_list(context):
    before = all_eligible(context)
    before_ids = [item["donation_id"] for item in before]

    assert set(context.ids.values()).issubset(before_ids)
    assert context.hidden.isdisjoint(before_ids)

    filtered = get_page(
        context,
        city=context.city_a,
        category=context.category_a,
        min_quantity="4",
    )
    assert_matches(context, filtered, ["a"])

    # API reset means omitting the optional filter query parameters.
    after = all_eligible(context)
    after_ids = [item["donation_id"] for item in after]

    assert after_ids == before_ids
    assert context.hidden.isdisjoint(after_ids)


def test_filtered_pagination_counts_and_order(context):
    params = {
        "city": context.city_a,
        "page_size": 1,
        "sort": "pickup_deadline",
    }

    first = get_page(context, **params, page=1)
    second = get_page(context, **params, page=2)
    third = get_page(context, **params, page=3)

    assert [row["donation_id"] for row in first["data"]] == [
        context.ids["a"]
    ]
    assert [row["donation_id"] for row in second["data"]] == [
        context.ids["b"]
    ]
    assert third["data"] == []

    for page in (first, second, third):
        assert page["pagination"]["total_items"] == 2
        assert page["pagination"]["total_pages"] == 2