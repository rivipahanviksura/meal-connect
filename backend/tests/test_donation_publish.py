
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.donation_lifecycle import (
    APIException,
    DonationStatus,
    publish_donation,
)

from fastapi.testclient import TestClient
from app.main import app

from app.api.dependencies import get_current_user
from app.db.models.user import UserRole, AccountStatus
from app.db.models.organization import (
    OrganizationType,
    VerificationStatus,
    MembershipRole,
    MemberStatus,
)
from app.db.session import get_db

def make_donation(
    status=DonationStatus.draft,
    expired=False,
):
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        donation_id=7,
        organization_id=10,
        created_by_user_id=1,
        title="Rice packets",
        category="prepared_meal",
        description="MEAL-226 test donation",
        total_quantity=Decimal("50"),
        allocated_quantity=Decimal("0"),
        quantity_unit="portions",
        allergen_info=None,
        storage_instructions=None,
        prepared_at=None,
        available_from=now - timedelta(hours=2),
        pickup_deadline=(
            now - timedelta(hours=1)
            if expired
            else now + timedelta(hours=3)
        ),
        pickup_address="Colombo",
        pickup_city="Colombo",
        status=status,
        created_at=now,
        updated_at=now - timedelta(minutes=10),
    )


# TC-01: Publish a valid draft donation.
def test_publish_valid_draft():
    db = MagicMock()
    item = make_donation()
    original_updated_at = item.updated_at
    db.scalar.return_value = item

    result = publish_donation(
        db=db,
        donation_id=7,
        organization_id=10,
        user_id=1,
    )

    assert result.status == DonationStatus.available
    assert result.updated_at > original_updated_at
    assert result.total_quantity == Decimal("50")
    assert result.allocated_quantity == Decimal("0")

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


# TC-05/06: Donation not owned or not found.
def test_publish_not_found():
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(APIException) as exc:
        publish_donation(
            db=db,
            donation_id=7,
            organization_id=999,
            user_id=1,
        )

    assert exc.value.status_code == 404

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# TC-07: Reject an expired draft.
def test_publish_expired_draft():
    db = MagicMock()
    item = make_donation(expired=True)
    db.scalar.return_value = item

    with pytest.raises(APIException) as exc:
        publish_donation(
            db=db,
            donation_id=7,
            organization_id=10,
            user_id=1,
        )

    assert exc.value.status_code == 409
    assert item.status == DonationStatus.draft

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# TC-08/09: Reject unsupported status transitions.
@pytest.mark.parametrize(
    "donation_status",
    [
        DonationStatus.available,
        DonationStatus.cancelled,
        DonationStatus.expired,
        DonationStatus.fully_allocated,
        DonationStatus.partially_allocated,
        DonationStatus.collected,
    ],
)
def test_publish_invalid_status(donation_status):
    db = MagicMock()
    item = make_donation(status=donation_status)
    db.scalar.return_value = item

    with pytest.raises(APIException) as exc:
        publish_donation(
            db=db,
            donation_id=7,
            organization_id=10,
            user_id=1,
        )

    assert exc.value.status_code == 409
    assert item.status == donation_status

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# TC-10: Validate required donation fields.
@pytest.mark.parametrize(
    "field,value",
    [
        ("title", ""),
        ("category", ""),
        ("quantity_unit", ""),
        ("total_quantity", Decimal("0")),
        ("total_quantity", Decimal("-5")),
        ("pickup_address", ""),
        ("pickup_city", ""),
    ],
)
def test_publish_invalid_required_fields(field, value):
    db = MagicMock()
    item = make_donation()

    setattr(item, field, value)
    db.scalar.return_value = item

    with pytest.raises(APIException) as exc:
        publish_donation(
            db=db,
            donation_id=7,
            organization_id=10,
            user_id=1,
        )

    assert exc.value.status_code == 422
    assert item.status == DonationStatus.draft

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# Validate the donation availability time window.
def test_publish_invalid_availability_window():
    db = MagicMock()
    item = make_donation()

    item.available_from = (
        item.pickup_deadline + timedelta(hours=1)
    )

    db.scalar.return_value = item

    with pytest.raises(APIException) as exc:
        publish_donation(
            db=db,
            donation_id=7,
            organization_id=10,
            user_id=1,
        )

    assert exc.value.status_code == 422
    assert item.status == DonationStatus.draft

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# Future availability is allowed before the deadline.
def test_publish_future_availability():
    db = MagicMock()
    item = make_donation()

    item.available_from = (
        datetime.now(timezone.utc) + timedelta(hours=1)
    )

    db.scalar.return_value = item

    result = publish_donation(
        db=db,
        donation_id=7,
        organization_id=10,
        user_id=1,
    )

    assert result.status == DonationStatus.available
    db.commit.assert_called_once()


# TC-11: Verify audit history.
def test_publish_records_status_history():
    db = MagicMock()
    item = make_donation()
    db.scalar.return_value = item

    result = publish_donation(
        db=db,
        donation_id=7,
        organization_id=10,
        user_id=5,
    )

    assert result.status == DonationStatus.available

    db.add.assert_called_once()

    history = db.add.call_args.args[0]

    assert history.entity_type == "donation"
    assert history.entity_id == 7
    assert history.old_status == "draft"
    assert history.new_status == "available"
    assert history.changed_by_user_id == 5
    assert history.change_reason == "Donation published."

    db.commit.assert_called_once()


# TC-13: Rollback on database transaction failure.
def test_publish_rollback_on_database_error():
    db = MagicMock()
    db.scalar.return_value = make_donation()

    db.commit.side_effect = RuntimeError(
        "Test transaction failed"
    )

    with pytest.raises(
        RuntimeError,
        match="Test transaction failed",
    ):
        publish_donation(
            db=db,
            donation_id=7,
            organization_id=10,
            user_id=1,
        )

    db.commit.assert_called_once()
    db.rollback.assert_called_once()


def test_publish_requires_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/donations/7/publish"
        )

    assert response.status_code == 401


def test_publish_route_registered():
    paths = app.openapi()["paths"]

    path = "/api/v1/donations/{donation_id}/publish"

    assert path in paths
    assert "post" in paths[path]
    assert "200" in paths[path]["post"]["responses"]


@pytest.fixture
def publish_api_client():
    original_overrides = app.dependency_overrides.copy()

    def create_client(
        role=UserRole.business_staff,
        verification_status=VerificationStatus.approved,
        organization_id=10,
        item=None,
    ):
        fake_user = SimpleNamespace(
            user_id=1,
            role=role,
            account_status=AccountStatus.active,
        )

        fake_org = SimpleNamespace(
            organization_id=organization_id,
            type=(
                OrganizationType.ngo
                if role == UserRole.ngo_staff
                else OrganizationType.restaurant
            ),
            verification_status=verification_status,
        )

        fake_membership = SimpleNamespace(
            membership_role=MembershipRole.staff,
            member_status=MemberStatus.active,
        )

        db = MagicMock()

        db.execute.return_value.all.return_value = [
            (fake_membership, fake_org)
        ]

        def mock_scalar(statement):
            if item is None:
                return None

            params = statement.compile().params

            if (
                params.get("donation_id_1") == item.donation_id
                and params.get("organization_id_1")
                == item.organization_id
            ):
                return item

            return None

        db.scalar.side_effect = mock_scalar

        def fake_get_db():
            yield db

        app.dependency_overrides[get_current_user] = (
            lambda: fake_user
        )

        app.dependency_overrides[get_db] = fake_get_db

        return TestClient(app), db

    yield create_client

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


# Approved Restaurant can publish its own draft.
def test_publish_api_success(publish_api_client):
    item = make_donation()

    client, db = publish_api_client(item=item)

    with client:
        response = client.post(
            "/api/v1/donations/7/publish"
        )

    assert response.status_code == 200, response.text

    data = response.json()["data"]

    assert data["donation_id"] == 7
    assert data["status"] == "available"
    assert data["organization_id"] == 10

    db.commit.assert_called_once()


# NGO and Admin cannot publish donations.
@pytest.mark.parametrize(
    "role",
    [
        UserRole.ngo_staff,
        UserRole.admin,
    ],
)
def test_publish_api_wrong_role(
    publish_api_client, role
):
    client, db = publish_api_client(
        role=role,
        item=make_donation(),
    )

    with client:
        response = client.post(
            "/api/v1/donations/7/publish"
        )

    assert response.status_code == 403, response.text
    db.commit.assert_not_called()
    db.add.assert_not_called()


# Unverified organizations cannot publish donations.
@pytest.mark.parametrize(
    "verification_status",
    [
        VerificationStatus.pending,
        VerificationStatus.rejected,
    ],
)
def test_publish_api_unverified_organization(
    publish_api_client,
    verification_status,
):
    item = make_donation()

    client, db = publish_api_client(
        verification_status=verification_status,
        item=item,
    )

    with client:
        response = client.post(
            "/api/v1/donations/7/publish"
        )

    assert response.status_code == 403, response.text
    assert item.status == DonationStatus.draft

    db.commit.assert_not_called()
    db.add.assert_not_called()


# Another Restaurant cannot publish the donation.
def test_publish_api_other_organization(
    publish_api_client,
):
    item = make_donation()

    client, db = publish_api_client(
        organization_id=20,
        item=item,
    )

    with client:
        response = client.post(
            "/api/v1/donations/7/publish"
        )

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert item.status == DonationStatus.draft

    db.commit.assert_not_called()
    db.add.assert_not_called()


# Nonexistent donation returns 404.
def test_publish_api_nonexistent_donation(
    publish_api_client,
):
    client, db = publish_api_client(item=None)

    with client:
        response = client.post(
            "/api/v1/donations/999/publish"
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"

    db.commit.assert_not_called()


# Invalid donation IDs are rejected.
@pytest.mark.parametrize(
    "donation_id",
    ["0", "-1", "abc", "9223372036854775808"],
)
def test_publish_api_invalid_id(
    publish_api_client,
    donation_id,
):
    client, db = publish_api_client(
        item=make_donation()
    )

    with client:
        response = client.post(
            f"/api/v1/donations/{donation_id}/publish"
        )

    assert response.status_code == 422, response.text

    db.commit.assert_not_called()
    db.add.assert_not_called()


# Expired drafts return the approved error code.
def test_publish_api_expired_draft(
    publish_api_client,
):
    item = make_donation(expired=True)

    client, db = publish_api_client(item=item)

    with client:
        response = client.post(
            "/api/v1/donations/7/publish"
        )

    assert response.status_code == 409
    assert (
        response.json()["error"]["code"]
        == "DONATION_EXPIRED"
    )

    assert item.status == DonationStatus.draft
    db.commit.assert_not_called()
    db.add.assert_not_called()


# Unsupported status transitions are rejected.
@pytest.mark.parametrize(
    "donation_status",
    [
        DonationStatus.available,
        DonationStatus.cancelled,
        DonationStatus.expired,
    ],
)
def test_publish_api_invalid_status(
    publish_api_client,
    donation_status,
):
    item = make_donation(status=donation_status)

    client, db = publish_api_client(item=item)

    with client:
        response = client.post(
            "/api/v1/donations/7/publish"
        )

    assert response.status_code == 409
    assert (
        response.json()["error"]["code"]
        == "INVALID_STATE_TRANSITION"
    )

    assert item.status == donation_status
    db.commit.assert_not_called()
    db.add.assert_not_called()
