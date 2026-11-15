
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_active_user,
    get_current_organization,
)
from app.api.donations import router
from app.core.exception_handlers import APIException
from app.db.models.user import UserRole
from app.db.session import get_db


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


def create_client(user, organization):
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_active_user] = lambda: user
    app.dependency_overrides[get_current_organization] = (
        lambda: organization
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()

    return TestClient(app)


def test_authorized_business_can_create_donation(monkeypatch):
    user = SimpleNamespace(
        user_id=1,
        role=UserRole.business_staff,
    )
    organization = SimpleNamespace(
        organization_id=10,
    )

    client = create_client(user, organization)
    mock_create = MagicMock(return_value={"donation_id": 100})

    monkeypatch.setattr(
        "app.api.donations.create_donation",
        mock_create,
    )

    response = client.post(
        "/donations/",
        json=valid_donation_payload(),
    )

    assert response.status_code == 201
    assert response.json()["donation_id"] == 100

    mock_create.assert_called_once()

    call_kwargs = mock_create.call_args.kwargs

    assert call_kwargs["current_user"] is user
    assert call_kwargs["organization"] is organization


def test_ngo_user_cannot_create_donation(monkeypatch):
    user = SimpleNamespace(
        user_id=2,
        role=UserRole.ngo_staff,
    )
    organization = SimpleNamespace(
        organization_id=20,
    )

    client = create_client(user, organization)
    mock_create = MagicMock()

    monkeypatch.setattr(
        "app.api.donations.create_donation",
        mock_create,
    )

    with pytest.raises(APIException) as exc_info:
        client.post(
            "/donations/",
            json=valid_donation_payload(),
        )

    assert exc_info.value.status_code == 403
    mock_create.assert_not_called()


def test_pending_organization_cannot_create_donation(monkeypatch):
    user = SimpleNamespace(
        user_id=3,
        role=UserRole.business_staff,
    )

    def reject_pending_organization():
        raise HTTPException(
            status_code=403,
            detail="Organization is not approved.",
        )

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_active_user] = lambda: user
    app.dependency_overrides[get_current_organization] = (
        reject_pending_organization
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()

    client = TestClient(app)
    mock_create = MagicMock()

    monkeypatch.setattr(
        "app.api.donations.create_donation",
        mock_create,
    )

    response = client.post(
        "/donations/",
        json=valid_donation_payload(),
    )

    assert response.status_code == 403
    mock_create.assert_not_called()

