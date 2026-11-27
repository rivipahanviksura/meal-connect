from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models.donation import Donation
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
        SecretStr("meal95-local-qa-signing-key-0123456789abcdef"),
    )
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")

    engine = get_engine()
    previous = app.dependency_overrides.copy()

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

                    def account(kind, role, suffix):
                        user = User(
                            first_name="MEAL95",
                            last_name="QA",
                            email=f"meal95-{unique}-{suffix}@example.com",
                            password_hash="fixture-only-not-a-login-password",
                            role=role,
                            account_status=AccountStatus.active,
                        )
                        organization = Organization(
                            name=f"MEAL95 {suffix} {unique}",
                            type=kind,
                            contact_email=user.email,
                            address_line="QA Test Road",
                            city="Kurunegala",
                            verification_status=VerificationStatus.approved,
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

                    owner, restaurant = account(
                        OrganizationType.restaurant,
                        UserRole.business_staff,
                        "restaurant",
                    )
                    ngo_user, ngo = account(
                        OrganizationType.ngo,
                        UserRole.ngo_staff,
                        "ngo",
                    )

                    db.commit()

                    def override_db():
                        yield db

                    app.dependency_overrides[get_db] = override_db

                    with TestClient(app) as client:
                        yield SimpleNamespace(
                            db=db,
                            client=client,
                            owner=owner,
                            restaurant=restaurant,
                            ngo_user=ngo_user,
                            ngo=ngo,
                        )
            finally:
                outer.rollback()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()


def valid_payload():
    now = datetime.now(timezone.utc)
    return {
        "title": "MEAL95 QA donation",
        "category": "prepared_meal",
        "total_quantity": "10.00",
        "quantity_unit": "portions",
        "available_from": (now + timedelta(days=1)).isoformat(),
        "pickup_deadline": (now + timedelta(days=2)).isoformat(),
        "pickup_address": "123 QA Test Road",
        "pickup_city": "Kurunegala",
        "status": "available",
    }


def headers(user):
    return {
        "Authorization": f"Bearer {create_access_token(user.user_id)}"
    }


def donation_count(context):
    # Count only records belonging to this test's synthetic users.
    return context.db.scalar(
        select(func.count())
        .select_from(Donation)
        .where(
            Donation.created_by_user_id.in_(
                [context.owner.user_id, context.ngo_user.user_id]
            )
        )
    )


def assert_rejected(context, response, status, code, before):
    assert response.status_code == status, response.text

    body = response.json()
    assert "data" not in body

    error = body["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert error["message"].strip()
    assert isinstance(error["fields"], list)

    # Confirm no write occurred; not merely an HTTP error.
    context.db.expire_all()
    assert donation_count(context) == before


@pytest.mark.parametrize(
    "field",
    [
        "title",
        "category",
        "total_quantity",
        "quantity_unit",
        "available_from",
        "pickup_deadline",
        "pickup_address",
        "pickup_city",
    ],
)
def test_missing_required_field_creates_no_record(context, field):
    payload = valid_payload()
    del payload[field]
    before = donation_count(context)

    response = context.client.post(
        "/api/v1/donations",
        json=payload,
        headers=headers(context.owner),
    )

    assert_rejected(
        context, response, 422, "VALIDATION_ERROR", before
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"total_quantity": "0"},
        {"total_quantity": "-1"},
        {"title": ""},
        {"title": "   "},
        {"category": ""},
        {"quantity_unit": ""},
        {"pickup_address": ""},
        {"pickup_city": ""},
        {"pickup_deadline": "not-a-date"},
        {"pickup_deadline": "2030-01-01T12:00:00"},
        {"status": "collected"},
    ],
    ids=[
        "zero-quantity",
        "negative-quantity",
        "empty-title",
        "whitespace-title",
        "empty-category",
        "empty-unit",
        "empty-address",
        "empty-city",
        "malformed-deadline",
        "deadline-without-timezone",
        "unsupported-status",
    ],
)
def test_invalid_values_create_no_record(context, changes):
    payload = {**valid_payload(), **changes}
    before = donation_count(context)

    response = context.client.post(
        "/api/v1/donations",
        json=payload,
        headers=headers(context.owner),
    )

    assert_rejected(
        context, response, 422, "VALIDATION_ERROR", before
    )


@pytest.mark.parametrize("offset_seconds", [0, -1])
def test_deadline_not_after_start_creates_no_record(
    context, offset_seconds
):
    payload = valid_payload()
    start = datetime.fromisoformat(payload["available_from"])
    payload["pickup_deadline"] = (
        start + timedelta(seconds=offset_seconds)
    ).isoformat()
    before = donation_count(context)

    response = context.client.post(
        "/api/v1/donations",
        json=payload,
        headers=headers(context.owner),
    )

    assert_rejected(
        context, response, 422, "VALIDATION_ERROR", before
    )


def test_elapsed_available_listing_creates_no_record(context):
    payload = valid_payload()
    payload["available_from"] = "2020-01-01T00:00:00Z"
    payload["pickup_deadline"] = "2020-01-02T00:00:00Z"
    before = donation_count(context)

    response = context.client.post(
        "/api/v1/donations",
        json=payload,
        headers=headers(context.owner),
    )

    assert_rejected(
        context, response, 409, "DONATION_EXPIRED", before
    )


def test_missing_authentication_creates_no_record(context):
    before = donation_count(context)

    response = context.client.post(
        "/api/v1/donations",
        json=valid_payload(),
    )

    assert_rejected(
        context, response, 401, "AUTH_REQUIRED", before
    )


def test_ngo_cannot_create_donation(context):
    before = donation_count(context)

    response = context.client.post(
        "/api/v1/donations",
        json=valid_payload(),
        headers=headers(context.ngo_user),
    )

    assert_rejected(
        context, response, 403, "FORBIDDEN", before
    )


@pytest.mark.parametrize(
    "verification",
    [
        VerificationStatus.pending,
        VerificationStatus.rejected,
        VerificationStatus.suspended,
    ],
)
def test_unverified_business_creates_no_record(context, verification):
    context.restaurant.verification_status = verification
    context.db.commit()
    before = donation_count(context)

    response = context.client.post(
        "/api/v1/donations",
        json=valid_payload(),
        headers=headers(context.owner),
    )

    assert_rejected(
        context, response, 403, "FORBIDDEN", before
    )


@pytest.mark.parametrize(
    "status",
    [AccountStatus.disabled, AccountStatus.suspended],
)
def test_inactive_account_creates_no_record(context, status):
    context.owner.account_status = status
    context.db.commit()
    before = donation_count(context)

    response = context.client.post(
        "/api/v1/donations",
        json=valid_payload(),
        headers=headers(context.owner),
    )

    assert_rejected(
        context, response, 403, "FORBIDDEN", before
    )


def test_other_organization_id_creates_no_record(context):
    payload = valid_payload()
    payload["organization_id"] = context.ngo.organization_id
    before = donation_count(context)

    response = context.client.post(
        "/api/v1/donations",
        json=payload,
        headers=headers(context.owner),
    )

    assert_rejected(
        context, response, 403, "FORBIDDEN", before
    )


def test_valid_creation_persists_expected_record(context):
    # Positive control: confirm the real write path works.
    before = donation_count(context)

    response = context.client.post(
        "/api/v1/donations",
        json=valid_payload(),
        headers=headers(context.owner),
    )

    assert response.status_code == 201, response.text
    data = response.json()["data"]

    context.db.expire_all()
    assert donation_count(context) == before + 1

    donation = context.db.get(Donation, data["donation_id"])
    assert donation is not None
    assert donation.organization_id == context.restaurant.organization_id
    assert donation.created_by_user_id == context.owner.user_id
    assert donation.total_quantity == Decimal("10.00")
    assert donation.allocated_quantity == Decimal("0.00")
    assert donation.status.value == "available"