
from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_active_user,
    require_roles,
)
from app.core.exception_handlers import register_exception_handlers
from app.db.models.user import UserRole


def create_test_client(role):
    app = FastAPI()
    register_exception_handlers(app)

    user = SimpleNamespace(role=role)

    app.dependency_overrides[get_active_user] = lambda: user

    @app.get("/admin-test")
    def admin_endpoint(
        admin=Depends(require_roles(UserRole.admin)),
    ):
        return {"message": "Admin access granted"}

    return TestClient(app)


def test_admin_role_allowed():
    client = create_test_client(UserRole.admin)

    response = client.get("/admin-test")

    assert response.status_code == 200


def test_restaurant_role_blocked():
    client = create_test_client(UserRole.business_staff)

    response = client.get("/admin-test")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_ngo_role_blocked():
    client = create_test_client(UserRole.ngo_staff)

    response = client.get("/admin-test")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

