
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_current_ngo_donation_request,
    get_current_organization,
)
from app.core.exception_handlers import register_exception_handlers
from app.db.models.organization import OrganizationType
from app.db.session import get_db


def create_organization(org_type=OrganizationType.ngo):
    return SimpleNamespace(
        organization_id=10,
        type=org_type,
    )


def create_donation_request(request_id=5, ngo_organization_id=10):
    return SimpleNamespace(
        request_id=request_id,
        ngo_organization_id=ngo_organization_id,
    )


def create_test_client(organization, donation_request):
    app = FastAPI()
    register_exception_handlers(app)

    app.dependency_overrides[get_current_organization] = (
        lambda: organization
    )

    def override_db():
        db = MagicMock()

        def mock_scalar(statement):
            if donation_request is None:
                return None

            params = statement.compile().params

            requested_id = params.get("request_id_1")
            requested_organization_id = params.get(
                "ngo_organization_id_1"
            )

            if (
                donation_request.request_id == requested_id
                and donation_request.ngo_organization_id
                == requested_organization_id
            ):
                return donation_request

            return None

        db.scalar.side_effect = mock_scalar
        return db

    app.dependency_overrides[get_db] = override_db

    @app.get("/requests/{request_id}")
    def request_endpoint(
        donation_request=Depends(
            get_current_ngo_donation_request
        ),
    ):
        return {
            "request_id": donation_request.request_id
        }

    return TestClient(app)


def test_own_ngo_request_is_allowed():
    organization = create_organization()
    donation_request = create_donation_request()

    client = create_test_client(
        organization,
        donation_request,
    )

    response = client.get("/requests/5")

    assert response.status_code == 200
    assert response.json() == {"request_id": 5}


def test_other_ngo_request_is_rejected():
    organization = create_organization()

    donation_request = create_donation_request(
        request_id=5,
        ngo_organization_id=20,
    )

    client = create_test_client(
        organization,
        donation_request,
    )

    response = client.get("/requests/5")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_missing_ngo_request_is_rejected():
    organization = create_organization()

    client = create_test_client(
        organization,
        None,
    )

    response = client.get("/requests/5")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_restaurant_cannot_use_ngo_request_dependency():
    organization = create_organization(
        org_type=OrganizationType.restaurant
    )

    donation_request = create_donation_request()

    client = create_test_client(
        organization,
        donation_request,
    )

    response = client.get("/requests/5")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
