
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
from app.db.models.user import UserRole, AccountStatus
from app.db.models.organization import (
    OrganizationType,
    VerificationStatus,
)
from app.db.models.donation_request import RequestStatus
from app.db.models.pickup import PickupStatus


@pytest.mark.parametrize(
    "organization_type",
    [OrganizationType.restaurant, OrganizationType.bakery],
)
def test_approved_business_allowed(organization_type):
    require_restaurant(
        UserRole.business_staff,
        AccountStatus.active,
        organization_type,
        VerificationStatus.approved,
    )


@pytest.mark.parametrize(
    "verification_status",
    [VerificationStatus.pending, VerificationStatus.rejected],
)
def test_unapproved_restaurant_blocked(verification_status):
    with pytest.raises(HTTPException) as error:
        require_restaurant(
            UserRole.business_staff,
            AccountStatus.active,
            OrganizationType.restaurant,
            verification_status,
        )
    assert error.value.status_code == 403


def test_ngo_cannot_use_restaurant_role():
    with pytest.raises(HTTPException):
        require_restaurant(
            UserRole.ngo_staff,
            AccountStatus.active,
            OrganizationType.ngo,
            VerificationStatus.approved,
        )


def test_approved_ngo_allowed():
    require_ngo(
        UserRole.ngo_staff,
        AccountStatus.active,
        OrganizationType.ngo,
        VerificationStatus.approved,
    )


@pytest.mark.parametrize(
    "verification_status",
    [VerificationStatus.pending, VerificationStatus.rejected],
)
def test_unapproved_ngo_blocked(verification_status):
    with pytest.raises(HTTPException) as error:
        require_ngo(
            UserRole.ngo_staff,
            AccountStatus.active,
            OrganizationType.ngo,
            verification_status,
        )
    assert error.value.status_code == 403


def test_admin_allowed():
    require_admin(UserRole.admin, AccountStatus.active)


def test_business_cannot_be_admin():
    with pytest.raises(HTTPException):
        require_admin(
            UserRole.business_staff,
            AccountStatus.active,
        )


def test_inactive_admin_blocked():
    with pytest.raises(HTTPException):
        require_admin(
            UserRole.admin,
            AccountStatus.suspended,
        )


def test_own_organization_allowed():
    require_ownership(1, 1)


def test_other_organization_blocked():
    with pytest.raises(HTTPException) as error:
        require_ownership(1, 2)
    assert error.value.status_code == 403


def test_own_approved_pickup_allowed():
    require_pickup_verification(
        1, 1, RequestStatus.approved
    )


def test_other_restaurant_pickup_blocked():
    with pytest.raises(HTTPException):
        require_pickup_verification(
            1, 2, RequestStatus.approved
        )


@pytest.mark.parametrize(
    "request_status",
    [
        RequestStatus.pending,
        RequestStatus.rejected,
        RequestStatus.cancelled,
        RequestStatus.fulfilled,
    ],
)
def test_unapproved_pickup_blocked(request_status):
    with pytest.raises(HTTPException) as error:
        require_pickup_verification(
            1, 1, request_status
        )
    assert error.value.status_code == 403


@pytest.mark.parametrize(
    "pickup_status",
    [PickupStatus.picked_up, PickupStatus.delivered],
)
def test_ngo_distribution_allowed(pickup_status):
    require_distribution_access(5, 5, pickup_status)


def test_other_ngo_distribution_blocked():
    with pytest.raises(HTTPException):
        require_distribution_access(
            5, 6, PickupStatus.picked_up
        )


@pytest.mark.parametrize(
    "pickup_status",
    [
        PickupStatus.assigned,
        PickupStatus.scheduled,
        PickupStatus.failed,
        PickupStatus.cancelled,
    ],
)
def test_distribution_before_collection_blocked(pickup_status):
    with pytest.raises(HTTPException) as error:
        require_distribution_access(
            5, 5, pickup_status
        )
    assert error.value.status_code == 403


def test_suspended_restaurant_blocked():
    with pytest.raises(HTTPException) as error:
        require_restaurant(
            UserRole.business_staff,
            AccountStatus.suspended,
            OrganizationType.restaurant,
            VerificationStatus.approved,
        )
    assert error.value.status_code == 403


def test_business_cannot_use_ngo_role():
    with pytest.raises(HTTPException) as error:
        require_ngo(
            UserRole.business_staff,
            AccountStatus.active,
            OrganizationType.restaurant,
            VerificationStatus.approved,
        )
    assert error.value.status_code == 403


def test_wrong_organization_type_blocked():
    with pytest.raises(HTTPException) as error:
        require_restaurant(
            UserRole.business_staff,
            AccountStatus.active,
            OrganizationType.ngo,
            VerificationStatus.approved,
        )
    assert error.value.status_code == 403
