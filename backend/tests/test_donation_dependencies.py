
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_active_user,
    get_current_donation,
    get_current_organization,
)
from app.core.exception_handlers import register_exception_handlers
from app.db.models.organization import (
    OrganizationType,
    VerificationStatus,
)
from app.db.models.user import UserRole
from app.db.session import get_db


def create_test_client(organization, donation, user=None):
    app = FastAPI()
    register_exception_handlers(app)

    if user is None:
        user = SimpleNamespace(
            user_id=1,
            role=UserRole.business_staff,
            account_status="active",
        )

    app.dependency_overrides[get_active_user] = lambda: user

    def override_organization():
        return organization

    def override_db():
        db = MagicMock()

        def mock_scalar(statement):
            if donation is None:
                return None

            params = statement.compile().params

            requested_donation_id = params.get("donation_id_1")
            requested_organization_id = params.get("organization_id_1")

            if (
                donation.donation_id == requested_donation_id
                and donation.organization_id == requested_organization_id
            ):
                return donation

            return None

        db.scalar.side_effect = mock_scalar
        return db

    app.dependency_overrides[get_current_organization] = override_organization
    app.dependency_overrides[get_db] = override_db

    @app.get("/donations/{donation_id}")
    def donation_endpoint(
        donation=Depends(get_current_donation),
    ):
        return {"donation_id": donation.donation_id}

    return TestClient(app)


def create_organization():
    return SimpleNamespace(
        organization_id=10,
        type=OrganizationType.restaurant,
        verification_status=VerificationStatus.approved,
    )


def create_donation(donation_id=5, organization_id=10):
    return SimpleNamespace(
        donation_id=donation_id,
        organization_id=organization_id,
    )


def test_own_donation_is_allowed():
    organization = create_organization()
    donation = create_donation()

    client = create_test_client(organization, donation)

    response = client.get("/donations/5")

    assert response.status_code == 200
    assert response.json() == {"donation_id": 5}


def test_missing_donation_is_rejected():
    organization = create_organization()

    client = create_test_client(organization, None)

    response = client.get("/donations/5")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_other_organization_donation_is_rejected():
    organization = create_organization()

    # This donation belongs to organization 20, not organization 10.
    donation = create_donation(
        donation_id=5,
        organization_id=20,
    )

    client = create_test_client(organization, donation)

    response = client.get("/donations/5")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
