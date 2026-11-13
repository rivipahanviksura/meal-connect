
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.auth as auth_api
from app.api.auth import router
from app.core.exception_handlers import (
    APIException,
    register_exception_handlers,
)
from app.db.models.user import UserRole, AccountStatus
from app.db.session import get_db


app = FastAPI()
register_exception_handlers(app)
app.include_router(router)

# Prevent tests from connecting to the real database.
app.dependency_overrides[get_db] = lambda: None

client = TestClient(app)


def create_user():
    return SimpleNamespace(
        user_id=1,
        first_name="Test",
        last_name="User",
        email="test@example.com",
        phone=None,
        role=UserRole.business_staff,
        account_status=AccountStatus.active,
    )


def test_login_success(monkeypatch):
    def mock_login_user(db, email, password):
        assert email == "test@example.com"
        assert password == "StrongPassword123"
        return "test-access-token", create_user()

    monkeypatch.setattr(auth_api, "login_user", mock_login_user)

    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "StrongPassword123",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["access_token"] == "test-access-token"
    assert data["token_type"] == "bearer"
    assert data["user"]["user_id"] == 1
    assert data["user"]["email"] == "test@example.com"

    # Password hash must never appear in the response.
    assert "password_hash" not in data["user"]


def test_login_invalid_credentials(monkeypatch):
    def mock_login_user(db, email, password):
        raise APIException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Invalid email or password.",
        )

    monkeypatch.setattr(auth_api, "login_user", mock_login_user)

    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_invalid_email_returns_422():
    response = client.post(
        "/auth/login",
        json={
            "email": "invalid-email",
            "password": "StrongPassword123",
        },
    )

    assert response.status_code == 422


def test_login_missing_password_returns_422():
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
        },
    )

    assert response.status_code == 422


def test_login_extra_fields_are_rejected():
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "StrongPassword123",
            "role": "admin",
        },
    )

    assert response.status_code == 422
