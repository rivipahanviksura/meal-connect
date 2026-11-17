from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import settings


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
    except (InvalidHashError, TypeError, ValueError):
        raise ValueError("Invalid stored password hash") from None


def verify_and_update(
    password: str,
    stored_hash: str,
) -> tuple[bool, str | None]:
    if not verify_password(password, stored_hash):
        return False, None

    if needs_rehash(stored_hash):
        return True, hash_password(password)

    return True, None


class TokenConfigurationError(RuntimeError):
    pass


def get_secret_key() -> str:
    key = settings.secret_key.get_secret_value() if settings.secret_key else ""

    if (
        not key
        or key.strip() == "REPLACE_WITH_LOCAL_RANDOM_SECRET"
        or len(key.encode("utf-8")) < 32
    ):
        raise TokenConfigurationError(
            "JWT signing key is missing or invalid."
        )

    return key


def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
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
        options={"require": ["exp", "sub"]},
    )
