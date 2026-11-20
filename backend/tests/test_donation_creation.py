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
    assert response_data["pickup_deadline"] == "2026-11-15T11:30:00Z"

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


@pytest.mark.parametrize("naive_fields", [
    ("available_from", "pickup_deadline", "prepared_at"),
    ("available_from",),
    ("pickup_deadline",),
    ("prepared_at",),
])
def test_naive_donation_timestamps_return_validation_error(client, naive_fields):
    payload = valid_donation_payload()
    for field in naive_fields:
        payload[field] = payload[field].removesuffix("+05:30")

    db = MagicMock()
    app.dependency_overrides[get_active_user] = create_user
    app.dependency_overrides[get_current_organization] = create_organization
    app.dependency_overrides[get_db] = lambda: db

    response = client.post("/api/v1/donations", json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert {field["field"] for field in error["fields"]} == set(naive_fields)
    db.add.assert_not_called()


def test_donation_cannot_be_created_for_a_different_organization(client):
    db = MagicMock()
    app.dependency_overrides[get_active_user] = create_user
    app.dependency_overrides[get_current_organization] = create_organization
    app.dependency_overrides[get_db] = lambda: db

    response = client.post("/api/v1/donations", json={
        **valid_donation_payload(), "organization_id": 99,
    })

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    db.add.assert_not_called()


def test_elapsed_deadline_cannot_create_an_available_donation(client):
    db = MagicMock()
    app.dependency_overrides[get_active_user] = create_user
    app.dependency_overrides[get_current_organization] = create_organization
    app.dependency_overrides[get_db] = lambda: db

    response = client.post("/api/v1/donations", json={
        **valid_donation_payload(),
        "organization_id": 10,
        "status": "available",
        "prepared_at": None,
        "available_from": "2020-01-01T00:00:00Z",
        "pickup_deadline": "2020-01-02T00:00:00Z",
    })

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DONATION_EXPIRED"
    db.add.assert_not_called()


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


@pytest.mark.parametrize(("field", "value"), [
    ("organization_id", True),
    ("organization_id", 2**63),
    ("description", "Invalid\x00text"),
    ("title", "   "),
    ("available_from", "0001-01-01T00:00:00+05:30"),
    ("status", "collected"),
    ("total_quantity", "1.001"),
])
def test_invalid_creation_fields_are_rejected_before_persistence(client, field, value):
    db = MagicMock()
    app.dependency_overrides[get_active_user] = create_user
    app.dependency_overrides[get_current_organization] = create_organization
    app.dependency_overrides[get_db] = lambda: db

    response = client.post(
        "/api/v1/donations", json={**valid_donation_payload(), field: value}
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in {entry["field"] for entry in error["fields"]}
    assert db.mock_calls == []


@pytest.mark.parametrize(("method", "suffix", "payload", "field"), [
    ("PATCH", "/100", {"title": "Invalid\x00title"}, "title"),
    ("PATCH", "/100", {"pickup_deadline": "9999-12-31T23:59:59-05:00"}, "pickup_deadline"),
    ("PATCH", "/100", {"status": "available"}, "status"),
    ("POST", "/100/cancel", {"reason": "Invalid\x00reason"}, "reason"),
])
def test_invalid_lifecycle_fields_are_rejected(client, method, suffix, payload, field):
    db = MagicMock()
    app.dependency_overrides[get_active_user] = create_user
    app.dependency_overrides[get_current_organization] = create_organization
    app.dependency_overrides[get_db] = lambda: db

    response = client.request(method, f"/api/v1/donations{suffix}", json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in {entry["field"] for entry in error["fields"]}
    assert db.mock_calls == []


@pytest.mark.parametrize(("changes", "field"), [
    ({"total_quantity": "0"}, "total_quantity"),
    ({"title": None}, "title"),
    ({"pickup_deadline": "2026-11-15T03:30:00Z"}, "request"),
])
def test_edit_validates_against_the_existing_donation(client, changes, field):
    db = MagicMock()
    donation = create_donation()
    db.scalar.return_value = donation
    app.dependency_overrides[get_active_user] = create_user
    app.dependency_overrides[get_current_organization] = create_organization
    app.dependency_overrides[get_db] = lambda: db

    response = client.patch("/api/v1/donations/100", json=changes)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in {entry["field"] for entry in error["fields"]}
    db.rollback.assert_called_once()
    db.commit.assert_not_called()
