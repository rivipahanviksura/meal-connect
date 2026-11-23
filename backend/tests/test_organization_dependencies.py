
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_active_user,
    get_current_organization,
)
from app.core.exception_handlers import register_exception_handlers
from app.db.models.organization import (
    MembershipRole,
    OrganizationType,
    VerificationStatus,
)
from app.db.models.user import UserRole


def create_client(user, db):
    app = FastAPI()
    register_exception_handlers(app)

    app.dependency_overrides[get_active_user] = lambda: user

    def override_db():
        return db

    from app.db.session import get_db
    app.dependency_overrides[get_db] = override_db

    @app.get("/organization")
    def organization_endpoint(
        organization=Depends(get_current_organization),
    ):
        return {
            "organization_id": organization.organization_id
        }

    return TestClient(app)


def create_user(role=UserRole.business_staff):
    return SimpleNamespace(
        user_id=1,
        role=role,
    )


def create_organization(
    org_type=OrganizationType.restaurant,
    status=VerificationStatus.approved,
):
    return SimpleNamespace(
        organization_id=10,
        type=org_type,
        verification_status=status,
    )


def create_db(organization=None, count=1, membership_role=MembershipRole.staff):
    db = MagicMock()

    if organization is None:
        db.execute.return_value.all.return_value = []
    else:
        results = [
            (SimpleNamespace(membership_role=membership_role), organization)
            for _ in range(count)
        ]
        db.execute.return_value.all.return_value = results

    return db


def test_approved_restaurant_is_allowed():
    user = create_user()
    organization = create_organization()
    db = create_db(organization)

    client = create_client(user, db)

    response = client.get("/organization")

    assert response.status_code == 200
    assert response.json() == {"organization_id": 10}


def test_pending_organization_is_rejected():
    user = create_user()
    organization = create_organization(
        status=VerificationStatus.pending
    )
    db = create_db(organization)

    client = create_client(user, db)

    response = client.get("/organization")

    assert response.status_code == 403


def test_business_user_cannot_access_ngo_organization():
    user = create_user()
    organization = create_organization(
        org_type=OrganizationType.ngo
    )
    db = create_db(organization)

    client = create_client(user, db)

    response = client.get("/organization")

    assert response.status_code == 403


def test_user_without_membership_is_rejected():
    user = create_user()
    db = create_db()

    client = create_client(user, db)

    response = client.get("/organization")

    assert response.status_code == 403


def test_user_with_multiple_active_memberships_is_rejected():
    user = create_user()
    organization = create_organization()
    db = create_db(organization, count=2)

    client = create_client(user, db)

    response = client.get("/organization")

    assert response.status_code == 403


def test_approved_ngo_is_allowed_for_ngo_user():
    user = create_user(role=UserRole.ngo_staff)
    organization = create_organization(
        org_type=OrganizationType.ngo
    )
    db = create_db(organization)

    client = create_client(user, db)

    response = client.get("/organization")

    assert response.status_code == 200
    assert response.json() == {"organization_id": 10}


def test_approved_bakery_is_allowed_for_business_user():
    user = create_user(role=UserRole.business_staff)
    organization = create_organization(
        org_type=OrganizationType.bakery
    )
    db = create_db(organization)

    client = create_client(user, db)

    response = client.get("/organization")

    assert response.status_code == 200
    assert response.json() == {"organization_id": 10}


def test_ngo_user_cannot_access_restaurant_organization():
    user = create_user(role=UserRole.ngo_staff)
    organization = create_organization(
        org_type=OrganizationType.restaurant
    )
    db = create_db(organization)

    client = create_client(user, db)

    response = client.get("/organization")

    assert response.status_code == 403


@pytest.mark.parametrize(
    "user_role, organization_type, membership_role, expected_status",
    [
        (UserRole.business_staff, OrganizationType.restaurant, MembershipRole.collector, 403),
        (UserRole.business_staff, OrganizationType.bakery, MembershipRole.coordinator, 403),
        (UserRole.ngo_staff, OrganizationType.ngo, MembershipRole.collector, 403),
        (UserRole.ngo_staff, OrganizationType.ngo, MembershipRole.coordinator, 200),
    ],
)
def test_membership_role_controls_organization_access(
    user_role, organization_type, membership_role, expected_status,
):
    user = create_user(role=user_role)
    db = create_db(create_organization(organization_type), membership_role=membership_role)

    response = create_client(user, db).get("/organization")

    assert response.status_code == expected_status
    if expected_status == 403:
        assert response.json()["error"]["code"] == "FORBIDDEN"


# MEAL-91: Rejected organizations cannot access protected operations.
@pytest.mark.parametrize(
    "organization_type,user_role",
    [
        (OrganizationType.restaurant, UserRole.business_staff),
        (OrganizationType.bakery, UserRole.business_staff),
        (OrganizationType.ngo, UserRole.ngo_staff),
    ],
)
def test_rejected_organization_cannot_access_protected_operation(
    organization_type,
    user_role,
):
    user = create_user(role=user_role)
    organization = create_organization(
        org_type=organization_type,
        status=VerificationStatus.rejected,
    )
    db = create_db(organization)

    with create_client(user, db) as client:
        response = client.get("/organization")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


# MEAL-91: Revoking verification blocks subsequent access.
def test_revoked_verification_blocks_subsequent_access():
    user = create_user(role=UserRole.business_staff)
    organization = create_organization(
        status=VerificationStatus.approved,
    )
    db = create_db(organization)

    with create_client(user, db) as client:
        before_revocation = client.get("/organization")

        assert before_revocation.status_code == 200

        organization.verification_status = VerificationStatus.suspended

        after_revocation = client.get("/organization")

    assert after_revocation.status_code == 403
    assert after_revocation.json()["error"]["code"] == "FORBIDDEN"

