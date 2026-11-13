
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.services.auth as auth_service
from app.core.exception_handlers import APIException
from app.db.models.user import AccountStatus, UserRole


def create_user(
    account_status=AccountStatus.active,
):
    return SimpleNamespace(
        user_id=1,
        email="test@example.com",
        password_hash="hashed-password",
        account_status=account_status,
        role=UserRole.business_staff,
    )


def create_db(user=None):
    db = MagicMock()
    db.scalar.return_value = user
    return db


def test_login_user_not_found():
    db = create_db(user=None)

    with pytest.raises(APIException) as exc:
        auth_service.login_user(
            db,
            "unknown@example.com",
            "StrongPassword123",
        )

    assert exc.value.status_code == 401
    assert exc.value.code == "INVALID_CREDENTIALS"


def test_login_wrong_password(monkeypatch):
    db = create_db(create_user())

    monkeypatch.setattr(
        auth_service,
        "verify_and_update",
        lambda password, stored_hash: (False, None),
    )

    with pytest.raises(APIException) as exc:
        auth_service.login_user(
            db,
            "test@example.com",
            "WrongPassword123",
        )

    assert exc.value.status_code == 401
    assert exc.value.code == "INVALID_CREDENTIALS"


def test_login_inactive_account(monkeypatch):
    db = create_db(
        create_user(AccountStatus.suspended)
    )

    monkeypatch.setattr(
        auth_service,
        "verify_and_update",
        lambda password, stored_hash: (True, None),
    )

    with pytest.raises(APIException) as exc:
        auth_service.login_user(
            db,
            "test@example.com",
            "StrongPassword123",
        )

    assert exc.value.status_code == 403
    assert exc.value.code == "ACCOUNT_INACTIVE"


def test_login_success(monkeypatch):
    user = create_user()
    db = create_db(user)

    monkeypatch.setattr(
        auth_service,
        "verify_and_update",
        lambda password, stored_hash: (True, None),
    )

    monkeypatch.setattr(
        auth_service,
        "create_access_token",
        lambda user_id: "test-access-token",
    )

    token, returned_user = auth_service.login_user(
        db,
        "test@example.com",
        "StrongPassword123",
    )

    assert token == "test-access-token"
    assert returned_user == user
    db.commit.assert_not_called()


def test_login_updates_password_hash(monkeypatch):
    user = create_user()
    db = create_db(user)

    monkeypatch.setattr(
        auth_service,
        "verify_and_update",
        lambda password, stored_hash: (
            True,
            "new-hashed-password",
        ),
    )

    monkeypatch.setattr(
        auth_service,
        "create_access_token",
        lambda user_id: "test-access-token",
    )

    auth_service.login_user(
        db,
        "test@example.com",
        "StrongPassword123",
    )

    assert user.password_hash == "new-hashed-password"
    db.commit.assert_called_once()
