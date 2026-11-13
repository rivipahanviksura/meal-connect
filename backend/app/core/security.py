
from datetime import datetime, timedelta, timezone

import jwt

from argon2 import PasswordHasher
from argon2.exceptions import (
    VerificationError,
    InvalidHashError,
)

from app.core.config import settings


# Password hashing
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return password_hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    try:
        return password_hasher.check_needs_rehash(stored_hash)
    except (VerificationError, InvalidHashError):
        return False


def verify_and_update(
    password: str,
    stored_hash: str,
) -> tuple[bool, str | None]:

    if not verify_password(password, stored_hash):
        return False, None

    if needs_rehash(stored_hash):
        return True, hash_password(password)

    return True, None


# JWT configuration
def get_secret_key() -> str:
    if settings.secret_key is None:
        raise RuntimeError("JWT SECRET_KEY is not configured.")

    return settings.secret_key.get_secret_value()


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": str(user_id),
        "exp": expire,
    }

    return jwt.encode(
        payload,
        get_secret_key(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        get_secret_key(),
        algorithms=[settings.jwt_algorithm],
    )
