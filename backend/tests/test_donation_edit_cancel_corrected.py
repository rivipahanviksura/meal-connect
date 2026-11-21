
"""MEAL-30: Donation edit and cancellation tests.

Run from backend:
py -m pytest -q tests/test_donation_edit_cancel_corrected.py
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.donation_edit_cancel import get_business_organization
from app.core.exception_handlers import APIException
from app.db.models.donation import DonationStatus
from app.db.session import get_db
from app.main import app
from app.schemas.donation_edit_cancel import (
    DonationCancel,
    DonationUpdate,
)
from app.services.donation_edit_cancel_service import (
    edit_donation,
    cancel_donation,
)


def donation(status=DonationStatus.draft, allocated="0"):
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        donation_id=7,
        organization_id=10,
        created_by_user_id=1,
        title="Rice packets",
        category="prepared_meal",
        description=None,
        total_quantity=Decimal("50"),
        allocated_quantity=Decimal(allocated),
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


def test_update_schema_rejects_empty_null_and_naive_dates():
    invalid_requests = (
        {},
        {"title": None},
        {"available_from": "2026-11-18T09:00:00"},
    )

    for kwargs in invalid_requests:
        with pytest.raises(ValidationError):
            DonationUpdate(**kwargs)


def test_cancel_reason_validation():
    with pytest.raises(ValidationError):
        DonationCancel(reason="x" * 501)

    result = DonationCancel(reason="Food spoiled")
    assert result.reason == "Food spoiled"


def test_edit_success_preserves_unset_fields():
    db = MagicMock()
    item = donation()
    db.scalar.return_value = item

    updated = edit_donation(
        db,
        7,
        10,
        DonationUpdate(title="New title"),
    )

    assert updated.title == "New title"
    assert updated.pickup_city == "Colombo"
    db.commit.assert_called_once()


def test_non_owner_returns_404_and_rolls_back():
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(APIException) as exc:
        edit_donation(
            db,
            7,
            999,
            DonationUpdate(title="No"),
        )

    assert exc.value.status_code == 404
    db.rollback.assert_called_once()


def test_cannot_change_location_after_pending_request():
    db = MagicMock()
    db.scalar.side_effect = [donation(), 23]

    with pytest.raises(APIException) as exc:
        edit_donation(
            db,
            7,
            10,
            DonationUpdate(pickup_city="Galle"),
        )

    assert exc.value.status_code == 409
    db.commit.assert_not_called()


def test_cannot_change_quantity_after_allocation():
    db = MagicMock()
    db.scalar.return_value = donation(allocated="10")

    with pytest.raises(APIException) as exc:
        edit_donation(
            db,
            7,
            10,
            DonationUpdate(
                total_quantity=Decimal("60")
            ),
        )

    assert exc.value.status_code == 409


def test_cross_field_timestamp_order_checked_in_utc():
    db = MagicMock()
    item = donation()
    db.scalar.return_value = item

    with pytest.raises(APIException) as exc:
        edit_donation(
            db,
            7,
            10,
            DonationUpdate(
                pickup_deadline=(
                    item.available_from
                    - timedelta(minutes=1)
                )
            ),
        )

    assert exc.value.status_code == 409
    db.commit.assert_not_called()


def test_cancel_rejects_pending_requests():
    db = MagicMock()
    db.scalar.side_effect = [donation(), 2]

    with pytest.raises(APIException) as exc:
        cancel_donation(
            db,
            7,
            10,
            changed_by_user_id=5,
        )

    assert exc.value.status_code == 409
    db.add.assert_not_called()


def test_cancel_rejects_active_pickup():
    db = MagicMock()
    db.scalar.side_effect = [donation(), None, 9]

    with pytest.raises(APIException) as exc:
        cancel_donation(
            db,
            7,
            10,
            changed_by_user_id=5,
        )

    assert exc.value.status_code == 409


def test_cancel_records_reason_and_actor_atomically():
    db = MagicMock()
    item = donation()
    db.scalar.side_effect = [item, None, None]

    cancelled = cancel_donation(
        db,
        7,
        10,
        changed_by_user_id=5,
        reason="Not available",
    )

    assert cancelled.status == DonationStatus.cancelled

    history = db.add.call_args.args[0]

    assert history.entity_type == "donation"
    assert history.old_status == "draft"
    assert history.new_status == "cancelled"
    assert history.change_reason == "Not available"
    assert history.changed_by_user_id == 5

    db.commit.assert_called_once()


def test_cancel_rollback_on_database_error():
    db = MagicMock()
    db.scalar.side_effect = [donation(), None, None]
    db.commit.side_effect = RuntimeError(
        "test transaction failed"
    )

    with pytest.raises(RuntimeError):
        cancel_donation(
            db,
            7,
            10,
            changed_by_user_id=5,
        )

    db.rollback.assert_called_once()


# FIXED: Validate registered endpoints through OpenAPI.
# This supports FastAPI versions with nested _IncludedRouter objects.
def test_existing_create_and_browse_routes_still_registered():
    paths = app.openapi()["paths"]

    donation_path = "/api/v1/donations"
    edit_path = "/api/v1/donations/{donation_id}"
    cancel_path = "/api/v1/donations/{donation_id}/cancel"

    assert donation_path in paths
    assert "post" in paths[donation_path]
    assert "get" in paths[donation_path]

    assert edit_path in paths
    assert "patch" in paths[edit_path]

    assert cancel_path in paths
    assert "post" in paths[cancel_path]


def test_anonymous_edit_and_cancel_rejected():
    with TestClient(app) as client:
        edit = client.patch(
            "/api/v1/donations/7",
            json={"title": "New"},
        )

        cancel = client.post(
            "/api/v1/donations/7/cancel",
            json={"reason": "Unavailable"},
        )

    assert edit.status_code == 401
    assert cancel.status_code == 401


def test_edit_api_response_keeps_data_wrapper():
    fake_org = SimpleNamespace(organization_id=10)

    db = MagicMock()
    db.scalar.return_value = donation()

    app.dependency_overrides[
        get_business_organization
    ] = lambda: fake_org

    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.patch(
                "/api/v1/donations/7",
                json={"title": "Updated"},
            )

        assert response.status_code == 200, response.text
        assert response.json()["data"]["title"] == "Updated"

    finally:
        app.dependency_overrides.pop(
            get_business_organization,
            None,
        )

        app.dependency_overrides.pop(
            get_db,
            None,
        )
