
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.meal11_permissions import (
    get_approved_restaurant_pickup_request,
    get_collected_ngo_request,
)
from app.core.exception_handlers import APIException
from app.db.models.donation_request import RequestStatus
from app.db.models.pickup import PickupStatus


def test_approved_restaurant_request_allowed():
    request = SimpleNamespace(
        request_id=5,
        status=RequestStatus.approved,
    )

    result = get_approved_restaurant_pickup_request(request)

    assert result == request


@pytest.mark.parametrize(
    "request_status",
    [
        RequestStatus.pending,
        RequestStatus.rejected,
        RequestStatus.cancelled,
        RequestStatus.fulfilled,
    ],
)
def test_unapproved_restaurant_request_blocked(request_status):
    request = SimpleNamespace(
        request_id=5,
        status=request_status,
    )

    with pytest.raises(APIException) as exc:
        get_approved_restaurant_pickup_request(request)

    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "pickup_status",
    [
        PickupStatus.picked_up,
        PickupStatus.delivered,
    ],
)
def test_collected_ngo_request_allowed(pickup_status):
    from unittest.mock import MagicMock

    request = SimpleNamespace(request_id=5)

    pickup = SimpleNamespace(
        status=pickup_status,
        pin_verified_at="verified",
        handover_confirmed_at="confirmed",
    )

    db = MagicMock()
    db.scalar.return_value = pickup

    result = get_collected_ngo_request(request, db)

    assert result == request


def test_ngo_distribution_blocked_before_collection():
    from unittest.mock import MagicMock

    request = SimpleNamespace(request_id=5)

    pickup = SimpleNamespace(
        status=PickupStatus.scheduled,
        pin_verified_at=None,
        handover_confirmed_at=None,
    )

    db = MagicMock()
    db.scalar.return_value = pickup

    with pytest.raises(APIException) as exc:
        get_collected_ngo_request(request, db)

    assert exc.value.status_code == 403


from unittest.mock import MagicMock


def test_distribution_blocked_without_pickup():
    request = SimpleNamespace(request_id=5)

    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(APIException) as exc:
        get_collected_ngo_request(request, db)

    assert exc.value.status_code == 403


def test_distribution_blocked_without_verified_pin():
    request = SimpleNamespace(request_id=5)

    pickup = SimpleNamespace(
        status=PickupStatus.picked_up,
        pin_verified_at=None,
        handover_confirmed_at="confirmed",
    )

    db = MagicMock()
    db.scalar.return_value = pickup

    with pytest.raises(APIException) as exc:
        get_collected_ngo_request(request, db)

    assert exc.value.status_code == 403


def test_distribution_blocked_without_handover():
    request = SimpleNamespace(request_id=5)

    pickup = SimpleNamespace(
        status=PickupStatus.picked_up,
        pin_verified_at="verified",
        handover_confirmed_at=None,
    )

    db = MagicMock()
    db.scalar.return_value = pickup

    with pytest.raises(APIException) as exc:
        get_collected_ngo_request(request, db)

    assert exc.value.status_code == 403
