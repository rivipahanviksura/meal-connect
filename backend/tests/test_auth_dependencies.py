
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import app.api.dependencies as auth_dependencies
from jwt.exceptions import InvalidTokenError

from app.api.dependencies import (
    get_active_user,
    get_current_user,
    require_roles,
)
from app.core.exception_handlers import register_exception_handlers
from app.db.models.user import AccountStatus, User, UserRole
from app.db.session import get_db


def create_test_client(user=None):
    app = FastAPI()

    register_exception_handlers(app)

    # Prevent tests from creating a real database connection.
    app.dependency_overrides[get_db] = lambda: None

    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user

    @app.get("/active")
    def active_endpoint(
        current_user: User = Depends(get_active_user),
    ):
        return {"user_id": current_user.user_id}

    @app.get("/admin")
    def admin_endpoint(
        current_user: User = Depends(require_roles(UserRole.admin)),
    ):
        return {"message": "Admin access granted"}

    return TestClient(app)


def create_test_user(
    role=UserRole.business_staff,
    status=AccountStatus.active,
):
    return User(
        user_id=1,
        first_name="Test",
        last_name="User",
        email="test@example.com",
        password_hash="test-hash",
        role=role,
        account_status=status,
    )


def test_missing_authentication_returns_401():
    client = create_test_client()

    response = client.get("/active")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_active_user_is_allowed():
    user = create_test_user()
    client = create_test_client(user)

    response = client.get("/active")

    assert response.status_code == 200
    assert response.json() == {"user_id": 1}


def test_inactive_user_is_rejected():
    user = create_test_user(status=AccountStatus.disabled)
    client = create_test_client(user)

    response = client.get("/active")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_role_is_allowed():
    user = create_test_user(role=UserRole.admin)
    client = create_test_client(user)

    response = client.get("/admin")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Admin access granted"
    }


def test_business_user_cannot_access_admin_endpoint():
    user = create_test_user(role=UserRole.business_staff)
    client = create_test_client(user)

    response = client.get("/admin")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"



class FakeDB:
    def __init__(self, user=None):
        self.user = user

    def get(self, model, user_id):
        if self.user and self.user.user_id == user_id:
            return self.user
        return None


def create_jwt_test_client(db):
    app = FastAPI()

    register_exception_handlers(app)

    app.dependency_overrides[get_db] = lambda: db

    @app.get("/current")
    def current_endpoint(
        current_user: User = Depends(get_current_user),
    ):
        return {"user_id": current_user.user_id}

    return TestClient(app)


def test_invalid_jwt_returns_401(monkeypatch):
    def invalid_token(token):
        raise InvalidTokenError("Invalid token")

    monkeypatch.setattr(
        auth_dependencies,
        "decode_access_token",
        invalid_token,
    )

    client = create_jwt_test_client(FakeDB())

    response = client.get(
        "/current",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_expired_jwt_returns_401(monkeypatch):
    def expired_token(token):
        raise InvalidTokenError("Token has expired")

    monkeypatch.setattr(
        auth_dependencies,
        "decode_access_token",
        expired_token,
    )

    client = create_jwt_test_client(FakeDB())

    response = client.get(
        "/current",
        headers={"Authorization": "Bearer expired-token"},
    )

    assert response.status_code == 401


def test_unknown_user_returns_401(monkeypatch):
    monkeypatch.setattr(
        auth_dependencies,
        "decode_access_token",
        lambda token: {"sub": "999"},
    )

    client = create_jwt_test_client(FakeDB())

    response = client.get(
        "/current",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 401


def test_valid_jwt_returns_current_user(monkeypatch):
    user = create_test_user()

    monkeypatch.setattr(
        auth_dependencies,
        "decode_access_token",
        lambda token: {"sub": "1"},
    )

    client = create_jwt_test_client(FakeDB(user))

    response = client.get(
        "/current",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": 1}

