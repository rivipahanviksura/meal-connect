
from fastapi import HTTPException, status

from app.db.models.user import UserRole, AccountStatus
from app.db.models.organization import (
    OrganizationType,
    VerificationStatus,
)
from app.db.models.donation_request import RequestStatus
from app.db.models.pickup import PickupStatus


def forbidden():
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permission denied",
    )


def require_role(role: UserRole, allowed_roles: set[UserRole]):
    if role not in allowed_roles:
        forbidden()


def require_active_account(account_status: AccountStatus):
    if account_status != AccountStatus.active:
        forbidden()


def require_verified_organization(
    verification_status: VerificationStatus,
):
    if verification_status != VerificationStatus.approved:
        forbidden()


def require_ownership(
    user_organization_id: int,
    resource_organization_id: int,
):
    if user_organization_id != resource_organization_id:
        forbidden()


def require_restaurant(
    role: UserRole,
    account_status: AccountStatus,
    organization_type: OrganizationType,
    verification_status: VerificationStatus,
):
    require_role(role, {UserRole.business_staff})
    require_active_account(account_status)

    if organization_type not in {
        OrganizationType.restaurant,
        OrganizationType.bakery,
    }:
        forbidden()

    require_verified_organization(verification_status)


def require_ngo(
    role: UserRole,
    account_status: AccountStatus,
    organization_type: OrganizationType,
    verification_status: VerificationStatus,
):
    require_role(role, {UserRole.ngo_staff})
    require_active_account(account_status)

    if organization_type != OrganizationType.ngo:
        forbidden()

    require_verified_organization(verification_status)


def require_admin(
    role: UserRole,
    account_status: AccountStatus,
):
    require_role(role, {UserRole.admin})
    require_active_account(account_status)


def require_pickup_verification(
    restaurant_organization_id: int,
    donation_organization_id: int,
    request_status: RequestStatus,
):
    require_ownership(
        restaurant_organization_id,
        donation_organization_id,
    )

    if request_status != RequestStatus.approved:
        forbidden()


def require_distribution_access(
    ngo_organization_id: int,
    request_ngo_organization_id: int,
    pickup_status: PickupStatus,
):
    require_ownership(
        ngo_organization_id,
        request_ngo_organization_id,
    )

    if pickup_status not in {
        PickupStatus.picked_up,
        PickupStatus.delivered,
    }:
        forbidden()
