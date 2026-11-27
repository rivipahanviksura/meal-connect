from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.dependencies import get_active_user
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.security import create_access_token
from app.db.models.user import AccountStatus, User, UserRole
from app.db.session import get_db


TEST_KEY = "meal215-test-only-signing-key-0123456789abcdef"
OTHER_KEY = "meal215-different-signing-key-0123456789abcdef"


class FakeDB:
    def __init__(self, user):
        self.user = user
        self.lookup_count = 0

    def get(self, model, user_id):
        self.lookup_count += 1

        if (
            model is User
            and self.user is not None
            and self.user.user_id == user_id
        ):
            return self.user

        return None


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setattr(
        settings,
        "secret_key",
        SecretStr(TEST_KEY),
    )
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(
        settings,
        "access_token_expire_minutes",
        15,
    )

    user = User(
        user_id=101,
        first_name="QA",
        last_name="Applicant",
        email="qa@example.com",
        password_hash="private-test-hash",
        role=UserRole.ngo_staff,
        account_status=AccountStatus.active,
    )

    db = FakeDB(user)

    # Test-only route exercises real production dependencies.
    # It is not added to the production application.
    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.dependency_overrides[get_db] = lambda: db

    @test_app.get("/qa/protected")
    def protected(
        current_user: User = Depends(get_active_user),
    ):
        return {"data": {"user_id": current_user.user_id}}

    with TestClient(test_app) as client:
        yield client, db


def assert_safe_error(response, status_code, code, token=None):
    assert response.status_code == status_code

    error = response.json()["error"]

    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert error["message"]
    assert error["fields"] == []

    assert "private-test-hash" not in response.text
    assert TEST_KEY not in response.text
    assert OTHER_KEY not in response.text
    assert "Traceback" not in response.text

    if token:
        assert token not in response.text


@pytest.mark.parametrize(
    "role",
    [UserRole.business_staff, UserRole.ngo_staff],
)
def test_real_access_token_allows_active_account(auth_client, role):
    client, db = auth_client
    db.user.role = role

    token = create_access_token(db.user.user_id)

    response = client.get(
        "/qa/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"data": {"user_id": 101}}
    assert db.lookup_count == 1
    assert "private-test-hash" not in response.text
    assert token not in response.text


@pytest.mark.parametrize(
    "case",
    [
        "expired",
        "wrong_signature",
        "missing_exp",
        "missing_sub",
        "invalid_sub",
        "zero_sub",
    ],
)
def test_unusable_signed_tokens_are_rejected(auth_client, case):
    client, db = auth_client

    now = datetime.now(timezone.utc)
    payload = {
        "sub": "101",
        "exp": now + timedelta(minutes=5),
    }
    signing_key = TEST_KEY

    if case == "expired":
        payload["exp"] = now - timedelta(minutes=5)
    elif case == "wrong_signature":
        signing_key = OTHER_KEY
    elif case == "missing_exp":
        del payload["exp"]
    elif case == "missing_sub":
        del payload["sub"]
    elif case == "invalid_sub":
        payload["sub"] = "not-a-user-id"
    elif case == "zero_sub":
        payload["sub"] = "0"

    token = jwt.encode(
        payload,
        signing_key,
        algorithm="HS256",
    )

    response = client.get(
        "/qa/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert_safe_error(
        response,
        401,
        "AUTH_REQUIRED",
        token,
    )

    # Invalid credentials must fail before querying the user.
    assert db.lookup_count == 0


@pytest.mark.parametrize(
    "status",
    [AccountStatus.disabled, AccountStatus.suspended],
)
def test_valid_token_cannot_bypass_inactive_account(auth_client, status):
    client, db = auth_client
    db.user.account_status = status

    token = create_access_token(db.user.user_id)

    response = client.get(
        "/qa/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert_safe_error(
        response,
        403,
        "FORBIDDEN",
        token,
    )
    assert db.lookup_count == 1


def test_signed_token_for_unknown_user_is_rejected(auth_client):
    client, db = auth_client

    token = create_access_token(999)

    response = client.get(
        "/qa/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert_safe_error(
        response,
        401,
        "AUTH_REQUIRED",
        token,
    )
    assert db.lookup_count == 1


def test_missing_token_returns_safe_401(auth_client):
    client, db = auth_client

    response = client.get("/qa/protected")

    assert_safe_error(response, 401, "AUTH_REQUIRED")
    assert db.lookup_count == 0