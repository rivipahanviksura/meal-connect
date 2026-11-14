from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.services.auth as auth_service
from app.db.models.user import AccountStatus, UserRole


def create_user(account_status=AccountStatus.active):
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
    db = create_db()
    with pytest.raises(auth_service.InvalidCredentialsError):
        auth_service.authenticate_user(db, "unknown@example.com", "StrongPassword123")


def test_login_wrong_password(monkeypatch):
    db = create_db(create_user())
    monkeypatch.setattr(auth_service, "verify_and_update", lambda p, h: (False, None))

    with pytest.raises(auth_service.InvalidCredentialsError):
        auth_service.authenticate_user(db, "test@example.com", "WrongPassword123")


def test_login_inactive_account(monkeypatch):
    db = create_db(create_user(AccountStatus.suspended))
    monkeypatch.setattr(auth_service, "verify_and_update", lambda p, h: (True, None))

    with pytest.raises(auth_service.InactiveAccountError):
        auth_service.authenticate_user(db, "test@example.com", "StrongPassword123")


def test_login_success(monkeypatch):
    user = create_user()
    db = create_db(user)
    monkeypatch.setattr(auth_service, "verify_and_update", lambda p, h: (True, None))

    returned_user = auth_service.authenticate_user(db, "test@example.com", "StrongPassword123")

    assert returned_user == user
    db.commit.assert_not_called()


def test_login_updates_password_hash(monkeypatch):
    user = create_user()
    db = create_db(user)
    monkeypatch.setattr(auth_service, "verify_and_update", lambda p, h: (True, "new-hashed-password"))

    auth_service.authenticate_user(db, "test@example.com", "StrongPassword123")

    assert user.password_hash == "new-hashed-password"
    db.commit.assert_called_once()
