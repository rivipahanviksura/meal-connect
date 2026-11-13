
import pytest
from fastapi import HTTPException

from app.core.rbac import (
    require_restaurant,
    require_ngo,
    require_admin,
    require_ownership,
    require_pickup_verification,
    require_distribution_access,
)


def test_restaurant_allowed():
    require_restaurant(
        "restaurant", "active", "restaurant", "approved"
    )


def test_pending_restaurant_blocked():
    with pytest.raises(HTTPException) as error:
        require_restaurant(
            "restaurant", "active", "restaurant", "pending"
        )
    assert error.value.status_code == 403


def test_rejected_restaurant_blocked():
    with pytest.raises(HTTPException):
        require_restaurant(
            "restaurant", "active", "restaurant", "rejected"
        )


def test_ngo_cannot_use_restaurant_role():
    with pytest.raises(HTTPException):
        require_restaurant(
            "ngo", "active", "ngo", "approved"
        )


def test_ngo_allowed():
    require_ngo("ngo", "active", "ngo", "approved")


def test_pending_ngo_blocked():
    with pytest.raises(HTTPException):
        require_ngo("ngo", "active", "ngo", "pending")


def test_admin_allowed():
    require_admin("admin", "active")


def test_restaurant_cannot_be_admin():
    with pytest.raises(HTTPException):
        require_admin("restaurant", "active")


def test_inactive_admin_blocked():
    with pytest.raises(HTTPException):
        require_admin("admin", "suspended")


def test_own_organization_allowed():
    require_ownership(1, 1)


def test_other_organization_blocked():
    with pytest.raises(HTTPException) as error:
        require_ownership(1, 2)
    assert error.value.status_code == 403


def test_own_approved_pickup_allowed():
    require_pickup_verification(1, 1, "approved")


def test_other_restaurant_pickup_blocked():
    with pytest.raises(HTTPException):
        require_pickup_verification(1, 2, "approved")


def test_pending_pickup_request_blocked():
    with pytest.raises(HTTPException):
        require_pickup_verification(1, 1, "pending")


def test_ngo_distribution_allowed():
    require_distribution_access(5, 5, "picked_up")


def test_other_ngo_distribution_blocked():
    with pytest.raises(HTTPException):
        require_distribution_access(5, 6, "picked_up")


def test_distribution_before_collection_blocked():
    with pytest.raises(HTTPException):
        require_distribution_access(5, 5, "scheduled")
