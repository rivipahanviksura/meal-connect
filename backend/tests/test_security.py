import pytest
from argon2 import PasswordHasher
from app.core.security import (
    hash_password,
    verify_password,
    needs_rehash,
    verify_and_update,
)


def test_password_is_hashed():
    password = "TestPassword@123"
    stored_hash = hash_password(password)

    assert stored_hash != password
    assert stored_hash.startswith("$argon2id$")


def test_correct_password():
    password = "TestPassword@123"
    stored_hash = hash_password(password)

    assert verify_password(password, stored_hash) is True


def test_wrong_password():
    stored_hash = hash_password("TestPassword@123")

    assert verify_password("WrongPassword", stored_hash) is False


def test_unique_salt():
    password = "TestPassword@123"

    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 != hash2


def test_invalid_hash():
    assert verify_password("TestPassword@123", "invalid") is False


def test_rehash_not_required():
    stored_hash = hash_password("TestPassword@123")

    assert needs_rehash(stored_hash) is False


def test_verify_and_update():
    stored_hash = hash_password("TestPassword@123")

    verified, new_hash = verify_and_update(
        "TestPassword@123", stored_hash
    )

    assert verified is True
    assert new_hash is None


def test_wrong_password_no_rehash():
    stored_hash = hash_password("TestPassword@123")

    verified, new_hash = verify_and_update(
        "WrongPassword", stored_hash
    )

    assert verified is False
    assert new_hash is None


def test_outdated_hash_requires_rehash():
    old_hasher = PasswordHasher(
        time_cost=1,
        memory_cost=1024,
        parallelism=1,
    )

    password = "TestPassword@123"
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

