from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.donations as donations_api
from app.api.dependencies import (
    get_active_user,
    get_current_organization,
)
from app.db.models.donation import DonationStatus
from app.db.models.organization import (
    OrganizationType,
    VerificationStatus,
)
from app.db.models.user import UserRole
from app.db.session import get_db
from app.main import app


def valid_donation_payload():
    return {
        "title": "Fresh Vegetables",
        "category": "Vegetables",
        "description": "Fresh surplus vegetables",
        "total_quantity": "25.50",
        "quantity_unit": "kg",
        "allergen_info": None,
        "storage_instructions": "Keep refrigerated",
        "prepared_at": "2026-11-15T08:00:00+05:30",
        "available_from": "2026-11-15T09:00:00+05:30",
        "pickup_deadline": "2026-11-15T17:00:00+05:30",
        "pickup_address": "Main Street",
        "pickup_city": "Colombo",
    }


def create_user(role=UserRole.business_staff):
    return SimpleNamespace(
        user_id=1,
        role=role,
    )


def create_organization(
    org_type=OrganizationType.restaurant,
    verification_status=VerificationStatus.approved,
):
    return SimpleNamespace(
        organization_id=10,
        type=org_type,
        verification_status=verification_status,
    )


def create_donation():
    now = datetime.fromisoformat("2026-11-15T09:00:00+05:30")

    return SimpleNamespace(
        donation_id=100,
        organization_id=10,
        created_by_user_id=1,
        title="Fresh Vegetables",
        category="Vegetables",
        description="Fresh surplus vegetables",
        total_quantity=Decimal("25.50"),
        allocated_quantity=Decimal("0.00"),
        quantity_unit="kg",
        allergen_info=None,
        storage_instructions="Keep refrigerated",
        prepared_at=datetime.fromisoformat("2026-11-15T08:00:00+05:30"),
        available_from=now,
        pickup_deadline=datetime.fromisoformat(
            "2026-11-15T17:00:00+05:30"
        ),
        pickup_address="Main Street",
        pickup_city="Colombo",
        status=DonationStatus.draft,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def client():
    app.dependency_overrides.clear()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_authorized_business_can_create_donation(client, monkeypatch):
    user = create_user()
    organization = create_organization()
    mock_create = MagicMock(return_value=create_donation())

    app.dependency_overrides[get_active_user] = lambda: user
    app.dependency_overrides[get_current_organization] = (
        lambda: organization
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()

    monkeypatch.setattr(
        donations_api,
        "create_donation",
        mock_create,
    )

    response = client.post(
        "/api/v1/donations",
        json=valid_donation_payload(),
    )

    assert response.status_code == 201

    response_data = response.json()["data"]

    assert response_data["donation_id"] == 100
    assert response_data["organization_id"] == 10
    assert response_data["created_by_user_id"] == 1
    assert response_data["title"] == "Fresh Vegetables"

    mock_create.assert_called_once()

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["current_user"] is user
    assert call_kwargs["organization"] is organization


def test_request_without_authentication_returns_401(client):
    app.dependency_overrides[get_db] = lambda: MagicMock()

    response = client.post(
        "/api/v1/donations",
        json=valid_donation_payload(),
    )

    assert response.status_code == 401
    assert "error" in response.json()


def test_ngo_user_cannot_create_donation(client, monkeypatch):
    user = create_user(role=UserRole.ngo_staff)
    organization = create_organization()
    mock_create = MagicMock()

    app.dependency_overrides[get_active_user] = lambda: user
    app.dependency_overrides[get_current_organization] = (
        lambda: organization
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()

    monkeypatch.setattr(
        donations_api,
        "create_donation",
        mock_create,
    )

    response = client.post(
        "/api/v1/donations",
        json=valid_donation_payload(),
    )

    assert response.status_code == 403
    mock_create.assert_not_called()


def test_pending_organization_cannot_create_donation(
    client,
    monkeypatch,
):
    user = create_user()
    pending_organization = create_organization(
        verification_status=VerificationStatus.pending,
    )

    db = MagicMock()
    db.execute.return_value.all.return_value = [
        (SimpleNamespace(), pending_organization)
    ]

    mock_create = MagicMock()

    app.dependency_overrides[get_active_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    monkeypatch.setattr(
        donations_api,
        "create_donation",
        mock_create,
    )

    response = client.post(
        "/api/v1/donations",
        json=valid_donation_payload(),
    )

    assert response.status_code == 403
    mock_create.assert_not_called()
