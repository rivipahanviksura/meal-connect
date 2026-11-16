
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.api.dependencies import get_current_user
from app.core.exception_handlers import APIException
from app.db.session import get_db
from app.db.models.donation import DonationStatus
from app.db.models.user import UserRole, AccountStatus
from app.db.models.organization import (
    OrganizationType,
    VerificationStatus,
    MemberStatus,
    MembershipRole,
)
from app.schemas.donation import DonationUpdate
from app.services.donation import edit_donation, cancel_donation


@pytest.fixture
def client():
    def fake_get_db():
        yield None

    app.dependency_overrides[get_db] = fake_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


# Helper: Create a fake donation
def make_donation(
    status=DonationStatus.draft,
    allocated=0,
):
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        donation_id=1,
        organization_id=10,
        created_by_user_id=30,
        title="Rice Packets",
        category="prepared_meal",
        description="Prepared today",
        total_quantity=Decimal("50"),
        allocated_quantity=Decimal(str(allocated)),
        quantity_unit="portions",
        allergen_info=None,
        storage_instructions=None,
        prepared_at=None,
        available_from=now,
        pickup_deadline=now + timedelta(hours=3),
        pickup_address="Colombo",
        pickup_city="Colombo",
        status=status,
        created_at=now,
        updated_at=now,
    )


# Test 1: Cannot edit without login
def test_edit_donation_without_login(client):
    response = client.patch(
        "/api/v1/donations/1",
        json={"title": "Updated Rice Packets"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


# Test 2: Cannot cancel without login
def test_cancel_donation_without_login(client):
    response = client.post(
        "/api/v1/donations/1/cancel",
        json={"reason": "Food no longer available"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


# Test 3: Invalid quantity validation
def test_edit_donation_invalid_data():
    with pytest.raises(ValidationError):
        DonationUpdate(total_quantity=-5)


# Test 4: Successful donation edit
def test_edit_donation_success():
    db = MagicMock()
    donation = make_donation()

    db.scalar.return_value = donation

    data = DonationUpdate(
        title="Updated Rice Packets"
    )

    result = edit_donation(
        db=db,
        donation_id=1,
        organization_id=10,
        data=data,
    )

    assert result.title == "Updated Rice Packets"
    db.commit.assert_called_once()


# Test 5: Collected donation cannot be edited
def test_edit_collected_donation_blocked():
    db = MagicMock()

    db.scalar.return_value = make_donation(
        status=DonationStatus.collected
    )

    data = DonationUpdate(title="Updated Food")

    with pytest.raises(APIException) as error:
        edit_donation(
            db=db,
            donation_id=1,
            organization_id=10,
            data=data,
        )

    assert error.value.status_code == 409
    db.commit.assert_not_called()


# Test 6: Cannot cancel an allocated donation
def test_cancel_donation_with_allocation_blocked():
    db = MagicMock()

    db.scalar.return_value = make_donation(
        status=DonationStatus.available,
        allocated=20,
    )

    with pytest.raises(APIException) as error:
        cancel_donation(
            db=db,
            donation_id=1,
            organization_id=10,
        )

    assert error.value.status_code == 409
    db.commit.assert_not_called()


# Test 7: Another organization's donation returns 404
def test_other_business_donation_not_found():
    db = MagicMock()
    db.scalar.return_value = None

    data = DonationUpdate(title="Updated Food")

    with pytest.raises(APIException) as error:
        edit_donation(
            db=db,
            donation_id=1,
            organization_id=99,
            data=data,
        )

    assert error.value.status_code == 404
    db.commit.assert_not_called()


# Test 8: Successful donation cancellation
def test_cancel_donation_success():
    db = MagicMock()
    donation = make_donation()

    # Donation exists, no active requests or pickups
    db.scalar.side_effect = [donation, None, None]

    result = cancel_donation(
        db=db,
        donation_id=1,
        organization_id=10,
    )

    assert result.status == DonationStatus.cancelled
    db.commit.assert_called_once()


# Test 9: Cannot change quantity after allocation
def test_edit_quantity_after_allocation_blocked():
    db = MagicMock()

    donation = make_donation(
        status=DonationStatus.available,
        allocated=20,
    )

    db.scalar.return_value = donation

    data = DonationUpdate(
        total_quantity=Decimal("60")
    )

    with pytest.raises(APIException) as error:
        edit_donation(
            db=db,
            donation_id=1,
            organization_id=10,
            data=data,
        )

    assert error.value.status_code == 409
    assert error.value.code == "INVALID_STATE_TRANSITION"
    db.commit.assert_not_called()


# Test 10: Cannot cancel when an active pickup exists
def test_cancel_donation_with_active_pickup_blocked():
    db = MagicMock()

    donation = make_donation(
        status=DonationStatus.available,
        allocated=0,
    )

    # Donation exists, no active requests, active pickup exists
    db.scalar.side_effect = [donation, None, 55]

    with pytest.raises(APIException) as error:
        cancel_donation(
            db=db,
            donation_id=1,
            organization_id=10,
        )

    assert error.value.status_code == 409
    assert error.value.code == "INVALID_STATE_TRANSITION"
    db.commit.assert_not_called()


# Test 11: NGO cannot edit a donation
def test_ngo_cannot_edit_donation():
    fake_ngo = SimpleNamespace(
        user_id=25,
        role=UserRole.ngo_staff,
        account_status=AccountStatus.active,
    )

    fake_organization = SimpleNamespace(
        organization_id=20,
        type=OrganizationType.ngo,
        verification_status=VerificationStatus.approved,
    )

    fake_membership = SimpleNamespace(
        membership_role=MembershipRole.staff,
        member_status=MemberStatus.active,
    )

    db = MagicMock()

    db.execute.return_value.all.return_value = [
        (fake_membership, fake_organization)
    ]

    def fake_get_db():
        yield db

    app.dependency_overrides[get_current_user] = lambda: fake_ngo
    app.dependency_overrides[get_db] = fake_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.patch(
                "/api/v1/donations/1",
                json={"title": "Changed by NGO"},
            )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


# Tests 12 and 13:
# Approved Restaurant and Bakery can edit their donations
@pytest.mark.parametrize(
    "organization_type",
    [
        OrganizationType.restaurant,
        OrganizationType.bakery,
    ],
)
def test_approved_business_can_edit_donation(organization_type):
    fake_user = SimpleNamespace(
        user_id=30,
        role=UserRole.business_staff,
        account_status=AccountStatus.active,
    )

    fake_organization = SimpleNamespace(
        organization_id=10,
        type=organization_type,
        verification_status=VerificationStatus.approved,
    )

    fake_membership = SimpleNamespace(
        membership_role=MembershipRole.staff,
        member_status=MemberStatus.active,
    )

    # Create a valid donation instead of returning MagicMock.
    donation = make_donation(
        status=DonationStatus.draft,
        allocated=0,
    )

    db = MagicMock()

    # Mock the active organization membership query.
    db.execute.return_value.all.return_value = [
        (fake_membership, fake_organization)
    ]

    # Mock the donation ownership query.
    db.scalar.return_value = donation

    def fake_get_db():
        yield db

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_db] = fake_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.patch(
                "/api/v1/donations/1",
                json={"title": "Updated Rice Packets"},
            )

        assert response.status_code == 200, response.text

        response_data = response.json()

        assert response_data["donation_id"] == 1
        assert response_data["organization_id"] == 10
        assert response_data["title"] == "Updated Rice Packets"
        assert response_data["status"] == "draft"

        db.commit.assert_called_once()

    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize(
    "organization_type",
    [
        OrganizationType.restaurant,
        OrganizationType.bakery,
    ],
)
def test_approved_business_can_cancel_donation(organization_type):
    fake_user = SimpleNamespace(
        user_id=30,
        role=UserRole.business_staff,
        account_status=AccountStatus.active,
    )

    fake_organization = SimpleNamespace(
        organization_id=10,
        type=organization_type,
        verification_status=VerificationStatus.approved,
    )

    fake_membership = SimpleNamespace(
        membership_role=MembershipRole.staff,
        member_status=MemberStatus.active,
    )

    donation = make_donation(
        status=DonationStatus.draft,
        allocated=0,
    )

    db = MagicMock()

    # Approved organization membership
    db.execute.return_value.all.return_value = [
        (fake_membership, fake_organization)
    ]

    # Donation exists, no active requests or pickups
    db.scalar.side_effect = [
        donation,
        None,
        None,
    ]

    def fake_get_db():
        yield db

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_db] = fake_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/donations/1/cancel",
                json={"reason": "Food is unavailable"},
            )

        assert response.status_code == 200, response.text
        assert response.json()["donation_id"] == 1
        assert response.json()["status"] == "cancelled"

        db.commit.assert_called_once()

    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_edit_invalid_pickup_deadline_blocked():
    db = MagicMock()
    donation = make_donation()

    db.scalar.return_value = donation

    invalid_deadline = donation.available_from - timedelta(hours=1)

    data = DonationUpdate(
        pickup_deadline=invalid_deadline
    )

    with pytest.raises(APIException) as error:
        edit_donation(
            db=db,
            donation_id=1,
            organization_id=10,
            data=data,
        )

    assert error.value.status_code == 409
    assert error.value.code == "INVALID_STATE_TRANSITION"
    db.commit.assert_not_called()
