
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from jwt.exceptions import InvalidTokenError

from app.core.exception_handlers import APIException
from app.core.security import decode_access_token
from app.db.session import get_db

from app.db.models.user import User, UserRole, AccountStatus

from app.db.models.organization import (
    Organization,
    OrganizationMembership,
    OrganizationType,
    VerificationStatus,
    MemberStatus,
)

from app.db.models.donation import Donation
from app.db.models.donation_request import DonationRequest


security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:

    if credentials is None:
        raise APIException(
            status_code=401,
            code="AUTH_REQUIRED",
            message="Authentication is required.",
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])

        if user_id <= 0:
            raise ValueError("Invalid user ID")

    except (InvalidTokenError, ValueError, TypeError, KeyError):
        raise APIException(
            status_code=401,
            code="AUTH_REQUIRED",
            message="Invalid or expired authentication token.",
        )

    user = db.get(User, user_id)

    if user is None:
        raise APIException(
            status_code=401,
            code="AUTH_REQUIRED",
            message="Authenticated user was not found.",
        )

    return user


def get_active_user(
    current_user: User = Depends(get_current_user),
) -> User:

    if current_user.account_status != AccountStatus.active:
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="Your account is not active.",
        )

    return current_user


def require_roles(*allowed_roles: UserRole):


    def role_checker(
        current_user: User = Depends(get_active_user),
    ) -> User:

        if current_user.role not in allowed_roles:
            raise APIException(
                status_code=403,
                code="FORBIDDEN",
                message="You do not have permission.",
            )

        return current_user

    return role_checker


def get_current_organization(
    current_user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
) -> Organization:


    # Map the user's role to the allowed organization types.
    if current_user.role == UserRole.business_staff:
        allowed_types = [
            OrganizationType.restaurant,
            OrganizationType.bakery,
        ]

    elif current_user.role == UserRole.ngo_staff:
        allowed_types = [
            OrganizationType.ngo,
        ]

    else:
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="You do not have permission to access an organization.",
        )

    # Find active memberships belonging to this user.
    statement = (
        select(OrganizationMembership, Organization)
        .join(
            Organization,
            Organization.organization_id
            == OrganizationMembership.organization_id,
        )
        .where(
            OrganizationMembership.user_id == current_user.user_id,
            OrganizationMembership.member_status == MemberStatus.active,
        )
    )

    results = db.execute(statement).all()

    # The user must have exactly one active organization.
    if len(results) != 1:
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="No valid organization membership was found.",
        )

    membership, organization = results[0]

    # Check organization type.
    if organization.type not in allowed_types:
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="Your account does not match this organization type.",
        )

    # Only approved organizations can use protected features.
    if organization.verification_status != VerificationStatus.approved:
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="Your organization is not approved.",
        )

    return organization


def get_current_donation(
    donation_id: int,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> Donation:


    statement = select(Donation).where(
        Donation.donation_id == donation_id,
        Donation.organization_id == organization.organization_id,
    )

    donation = db.scalar(statement)

    if donation is None:
        raise APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Donation not found.",
        )

    return donation


def get_current_ngo_donation_request(
    request_id: int,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> DonationRequest:


    if organization.type != OrganizationType.ngo:
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="Only NGO organizations can access donation requests.",
        )

    statement = select(DonationRequest).where(
        DonationRequest.request_id == request_id,
        DonationRequest.ngo_organization_id == organization.organization_id,
    )

    donation_request = db.scalar(statement)

    if donation_request is None:
        raise APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Donation request not found.",
        )

    return donation_request


def get_current_restaurant_donation_request(
    request_id: int,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> DonationRequest:


    if organization.type not in [
        OrganizationType.restaurant,
        OrganizationType.bakery,
    ]:
        raise APIException(
            status_code=403,
            code="FORBIDDEN",
            message="Only Restaurant organizations can manage donation requests.",
        )

    statement = (
        select(DonationRequest)
        .join(
            Donation,
            Donation.donation_id == DonationRequest.donation_id,
        )
        .where(
            DonationRequest.request_id == request_id,
            Donation.organization_id == organization.organization_id,
        )
    )

    donation_request = db.scalar(statement)

    if donation_request is None:
        raise APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Donation request not found.",
        )

    return donation_request
