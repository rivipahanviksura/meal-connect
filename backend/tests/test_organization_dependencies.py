
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_active_user,
    get_current_organization,
)
from app.core.exception_handlers import register_exception_handlers
from app.db.models.organization import (
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


def create_db(organization=None, count=1):
    db = MagicMock()

    if organization is None:
        db.execute.return_value.all.return_value = []
    else:
        results = [
            (SimpleNamespace(), organization)
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
