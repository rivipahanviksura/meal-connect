
from argon2 import PasswordHasher
from argon2.exceptions import (
    VerificationError,
    InvalidHashError,
)

# Argon2id is the default password-hashing algorithm.
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Return True only when the password matches."""
    try:
        return password_hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    """Check whether the stored hash uses outdated settings."""
    try:
        return password_hasher.check_needs_rehash(stored_hash)
    except (InvalidHashError, TypeError, ValueError):
        raise ValueError("Invalid stored password hash") from None


def verify_and_update(
    password: str,
    stored_hash: str,
) -> tuple[bool, str | None]:
    """Verify and optionally return a replacement hash."""
    if not verify_password(password, stored_hash):
        return False, None

    if needs_rehash(stored_hash):
        return True, hash_password(password)

    return True, None
