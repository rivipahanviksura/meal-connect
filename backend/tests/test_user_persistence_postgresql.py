from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.models.user import AccountStatus, User, UserRole
from app.db.session import get_engine
from app.schemas.user import RegistrationRequest
from app.services import user_service


@pytest.fixture
def postgres_engine():
    # Only the dedicated local test database is permitted.
    assert settings.database_url is not None

    url = make_url(settings.database_url.get_secret_value())

    assert url.get_backend_name() == "postgresql"
    assert url.database == "meal_connect_test"
    assert url.host in {"localhost", "127.0.0.1", "::1"}

    engine = get_engine()

    try:
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            assert database_name == "meal_connect_test"

        yield engine
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "account_type, expected_role",
    [
        ("business", UserRole.business_staff),
        ("ngo", UserRole.ngo_staff),
    ],
)
def test_concurrent_registration_persists_one_user(
    postgres_engine,
    monkeypatch,
    account_type,
    expected_role,
):
    email = f"meal214_{uuid4().hex}@example.com"
    password = "IntegrationTestPassword123!"
    stored_hash = hash_password(password)

    payload = RegistrationRequest(
        first_name="Concurrency",
        last_name="Test",
        email=email.upper(),
        password=password,
        account_type=account_type,
    )

    workers = 4
    barrier = Barrier(workers, timeout=15)

    original_lookup = user_service.get_user_by_email

    def synchronized_lookup(db, lookup_email):
        result = original_lookup(db, lookup_email)

        # Force all workers past the real database lookup before
        # any worker attempts insertion. No duplicate exception
        # or database constraint is mocked.
        barrier.wait()

        return result

    def register_once():
        # Each worker owns an independent database session.
        with Session(postgres_engine) as db:
            db.execute(
                text("SET LOCAL statement_timeout = '20s'")
            )
            db.execute(
                text("SET LOCAL lock_timeout = '10s'")
            )

            try:
                user = user_service.create_user_record(
                    db,
                    payload,
                    stored_hash,
                )
                return ("created", user.user_id)

            except user_service.DuplicateEmailError:
                # The service must have rolled back the failed
                # transaction, allowing the session to work again.
                assert db.scalar(text("SELECT 1")) == 1
                return ("duplicate", None)

    try:
        # The barrier is used only while concurrent workers run.
        with monkeypatch.context() as patch:
            patch.setattr(
                user_service,
                "get_user_by_email",
                synchronized_lookup,
            )

            with ThreadPoolExecutor(
                max_workers=workers
            ) as executor:
                futures = [
                    executor.submit(register_once)
                    for _ in range(workers)
                ]

                results = [
                    future.result(timeout=45)
                    for future in futures
                ]

        outcomes = [result[0] for result in results]

        assert outcomes.count("created") == 1
        assert outcomes.count("duplicate") == workers - 1

        # A separate session proves the record was committed
        # and is visible outside the creating session.
        with Session(postgres_engine) as db:
            count = db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.email == email)
            )
            assert count == 1

            user = original_lookup(
                db,
                f"  {email.upper()}  ",
            )

            assert user is not None
            assert user.email == email
            assert user.role == expected_role
            assert user.account_status == AccountStatus.active
            assert user.password_hash != password
            assert user.password_hash.startswith("$argon2id$")
            assert verify_password(
                password,
                user.password_hash,
            )

            created_ids = [
                user_id
                for outcome, user_id in results
                if outcome == "created"
            ]
            assert created_ids == [user.user_id]

    finally:
        # Remove only this test's unique user record.
        # Never truncate or reset existing tables.
        with Session(postgres_engine) as db:
            db.execute(
                delete(User).where(User.email == email)
            )
            db.commit()