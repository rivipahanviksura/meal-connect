from datetime import datetime, timedelta, timezone

import jwt
import pytest
from argon2 import PasswordHasher
from pydantic import SecretStr

from app.core.config import settings
from app.core.security import (
    TokenConfigurationError,
    create_access_token,
    decode_access_token,
    get_secret_key,
    hash_password,
    needs_rehash,
    verify_and_update,
    verify_password,
)


@pytest.fixture(autouse=True)
def test_secret_key(monkeypatch):
    monkeypatch.setattr(
        settings,
        "secret_key",
        SecretStr("test-only-secret-key-that-is-at-least-32-bytes"),
    )


def test_password_is_hashed():
    password = "StrongPassword123"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$argon2id$")


def test_correct_password_is_verified():
    hashed = hash_password("StrongPassword123")

    assert verify_password("StrongPassword123", hashed) is True


def test_wrong_password_is_rejected():
    hashed = hash_password("StrongPassword123")

    assert verify_password("WrongPassword123", hashed) is False


def test_unique_salt():
    password = "StrongPassword123"

    assert hash_password(password) != hash_password(password)


def test_invalid_hash_is_rejected():
    assert verify_password("password", "invalid-hash") is False


def test_needs_rehash_returns_boolean():
    hashed = hash_password("StrongPassword123")

    assert needs_rehash(hashed) is False


def test_verify_and_update_with_correct_password():
    password = "StrongPassword123"
    hashed = hash_password(password)

    valid, updated_hash = verify_and_update(password, hashed)

    assert valid is True
    assert updated_hash is None


def test_verify_and_update_with_wrong_password():
    hashed = hash_password("StrongPassword123")

    valid, updated_hash = verify_and_update(
        "WrongPassword123",
        hashed,
    )

    assert valid is False
    assert updated_hash is None


def test_outdated_hash_requires_rehash():
    old_hasher = PasswordHasher(
        time_cost=1,
        memory_cost=1024,
        parallelism=1,
    )
    password = "StrongPassword123"
    old_hash = old_hasher.hash(password)

    assert needs_rehash(old_hash) is True

    verified, new_hash = verify_and_update(password, old_hash)

    assert verified is True
    assert new_hash is not None
    assert new_hash != old_hash
    assert verify_password(password, new_hash) is True
    assert needs_rehash(new_hash) is False


def test_malformed_hash_rehash_handling():
    with pytest.raises(ValueError, match="Invalid stored password hash"):
        needs_rehash("invalid-hash")


def test_access_token_can_be_created_and_decoded():
    token = create_access_token(user_id=1)

    payload = decode_access_token(token)

    assert payload["sub"] == "1"
    assert "exp" in payload


def test_expired_token_is_rejected():
    expired_payload = {
        "sub": "1",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }

    token = jwt.encode(
        expired_payload,
        get_secret_key(),
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


@pytest.mark.parametrize(
    "secret",
    [
        None,
        SecretStr("REPLACE_WITH_LOCAL_RANDOM_SECRET"),
        SecretStr("too-short"),
    ],
)
def test_invalid_signing_key_is_rejected(monkeypatch, secret):
    monkeypatch.setattr(settings, "secret_key", secret)

    with pytest.raises(TokenConfigurationError):
        get_secret_key()


@pytest.mark.parametrize(
    "payload",
    [
        {"sub": "1"},
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
    ],
)
def test_token_missing_required_claim_is_rejected(payload):
    token = jwt.encode(
        payload,
        get_secret_key(),
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(token)
