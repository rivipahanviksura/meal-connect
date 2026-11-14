
from fastapi import HTTPException, status


def forbidden():
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permission denied"
    )


def require_role(role: str, allowed_roles: set[str]):
    if role not in allowed_roles:
        forbidden()


def require_active_account(account_status: str):
    if account_status != "active":
        forbidden()


def require_verified_organization(verification_status: str):
    if verification_status != "approved":
        forbidden()


def require_ownership(
    user_organization_id: int,
    resource_organization_id: int
):
    if user_organization_id != resource_organization_id:
        forbidden()


def require_restaurant(
    role: str,
    account_status: str,
    organization_type: str,
    verification_status: str
):
    require_role(role, {"restaurant"})
    require_active_account(account_status)

    if organization_type != "restaurant":
        forbidden()

    require_verified_organization(verification_status)


def require_ngo(
    role: str,
    account_status: str,
    organization_type: str,
    verification_status: str
):
    require_role(role, {"ngo"})
    require_active_account(account_status)

    if organization_type != "ngo":
        forbidden()

    require_verified_organization(verification_status)


def require_admin(role: str, account_status: str):
    require_role(role, {"admin"})
    require_active_account(account_status)


def require_pickup_verification(
    restaurant_organization_id: int,
    donation_organization_id: int,
    request_status: str
):
    require_ownership(
        restaurant_organization_id,
        donation_organization_id
    )

    if request_status != "approved":
        forbidden()


def require_distribution_access(
    ngo_organization_id: int,
    request_ngo_organization_id: int,
    pickup_status: str
):
    require_ownership(
        ngo_organization_id,
        request_ngo_organization_id
    )

    if pickup_status not in {"picked_up", "delivered"}:
        forbidden()
