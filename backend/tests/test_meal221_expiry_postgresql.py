from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import app.services.donation_browse_service as browse_service
import app.services.donation_detail_service as detail_service

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
from app.services.donation_availability import (
    DonationExpiredError,
    ensure_donation_not_expired,
)


NOW = datetime(2026, 11, 27, 10, 0, tzinfo=timezone.utc)


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return NOW.replace(tzinfo=None)
        return NOW.astimezone(tz)


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
            assert connection.execute(
                text("SELECT current_database()")
            ).scalar_one() == "meal_connect_test"

            connection.rollback()
            outer = connection.begin()

            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    yield session
            finally:
                outer.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(
        settings,
        "secret_key",
        SecretStr("meal221-local-test-key-0123456789abcdef"),
    )
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")

    # Freeze only discovery/detail clocks. JWT uses real time.
    monkeypatch.setattr(browse_service, "datetime", FrozenDateTime)
    monkeypatch.setattr(detail_service, "datetime", FrozenDateTime)

    previous = app.dependency_overrides.copy()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize(
    "status,allocated",
    [
        (DonationStatus.available, Decimal("0")),
        (DonationStatus.partially_allocated, Decimal("3")),
    ],
)
@pytest.mark.parametrize(
    "deadline_offset,visible",
    [
        (1, True),
        (0, False),
        (-1, False),
    ],
    ids=["before-deadline", "exact-deadline", "after-deadline"],
)
def test_deadline_controls_live_discovery_and_guard(
    db, client, status, allocated, deadline_offset, visible
):
    unique = uuid4().hex

    ngo_user = User(
        first_name="QA",
        last_name="NGO",
        email=f"meal221-ngo-{unique}@example.com",
        password_hash="fixture-only-no-password-login",
        role=UserRole.ngo_staff,
        account_status=AccountStatus.active,
    )
    donor_user = User(
        first_name="QA",
        last_name="Donor",
        email=f"meal221-donor-{unique}@example.com",
        password_hash="fixture-only-no-password-login",
        role=UserRole.business_staff,
        account_status=AccountStatus.active,
    )

    ngo = Organization(
        name=f"MEAL221 NGO {unique}",
        type=OrganizationType.ngo,
        contact_email=ngo_user.email,
        address_line="QA Road",
        city="Kurunegala",
        verification_status=VerificationStatus.approved,
    )
    donor = Organization(
        name=f"MEAL221 Restaurant {unique}",
        type=OrganizationType.restaurant,
        contact_email=donor_user.email,
        address_line="QA Road",
        city="Kurunegala",
        verification_status=VerificationStatus.approved,
    )

    db.add_all([ngo_user, donor_user, ngo, donor])
    db.flush()

    db.add(
        OrganizationMembership(
            organization_id=ngo.organization_id,
            user_id=ngo_user.user_id,
            membership_role=MembershipRole.owner,
            member_status=MemberStatus.active,
        )
    )

    donation = Donation(
        organization_id=donor.organization_id,
        created_by_user_id=donor_user.user_id,
        title=f"MEAL221 expiry {unique}",
        category=f"qa221_{unique}",
        total_quantity=Decimal("10"),
        allocated_quantity=allocated,
        quantity_unit="portions",
        available_from=NOW - timedelta(hours=1),
        pickup_deadline=NOW + timedelta(microseconds=deadline_offset),
        pickup_address="QA Road",
        pickup_city="Kurunegala",
        status=status,
    )

    db.add(donation)
    db.flush()

    donation_id = donation.donation_id
    category = donation.category
    user_id = ngo_user.user_id

    # Release the session savepoint; the outer transaction still rolls back.
    db.commit()

    headers = {
        "Authorization": f"Bearer {create_access_token(user_id)}"
    }

    listing = client.get(
        "/api/v1/donations",
        params={"category": category},
        headers=headers,
    )

    assert listing.status_code == 200
    body = listing.json()

    assert [item["donation_id"] for item in body["data"]] == (
        [donation_id] if visible else []
    )
    assert body["pagination"]["total_items"] == int(visible)

    detail = client.get(
        f"/api/v1/donations/{donation_id}",
        headers=headers,
    )

    if visible:
        assert detail.status_code == 200
        assert detail.json()["data"]["donation_id"] == donation_id
        ensure_donation_not_expired(donation, now=NOW)
    else:
        assert detail.status_code == 404
        assert detail.json()["error"]["code"] == "NOT_FOUND"

        with pytest.raises(DonationExpiredError):
            ensure_donation_not_expired(donation, now=NOW)

    # Discovery is read-time filtering; it must not rewrite stored status.
    db.refresh(donation)
    assert donation.status == status