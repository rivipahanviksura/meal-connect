
from datetime import datetime, timedelta, timezone

import jwt

from app.core.security import (
    hash_password,
    verify_password,
    needs_rehash,
    verify_and_update,
    create_access_token,
    decode_access_token,
    get_secret_key,
)
from app.core.config import settings


def test_password_is_hashed():
    password = "StrongPassword123"

    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$argon2id$")


def test_correct_password_is_verified():
    password = "StrongPassword123"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_wrong_password_is_rejected():
    hashed = hash_password("StrongPassword123")

    assert verify_password("WrongPassword123", hashed) is False


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

    try:
        decode_access_token(token)
        assert False, "Expired token should be rejected"
    except jwt.ExpiredSignatureError:
        pass
