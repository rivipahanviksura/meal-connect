"""Opt-in PostgreSQL integration tests for MEAL-85.

Required disposable databases:
- MEAL85_TEST_DATABASE_URL: database upgraded to revision 57cacefc56a2.
  It must contain duplicate registration numbers across different
  organization types, so the downgrade preflight can be tested.
- MEAL85_UPGRADE_TEST_DATABASE_URL: database at revision e721c958e76a
  containing at least one user with multiple organization memberships.

Both database names must start with "meal85_".
These tests never create or drop databases.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError


pytestmark = pytest.mark.skipif(
    not os.getenv("MEAL85_TEST_DATABASE_URL")
    or not os.getenv("MEAL85_UPGRADE_TEST_DATABASE_URL"),
    reason="Set both MEAL85_TEST_DATABASE_URL and "
    "MEAL85_UPGRADE_TEST_DATABASE_URL to run PostgreSQL integration tests.",
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
PARENT_REVISION = "e721c958e76a"
MEAL85_REVISION = "57cacefc56a2"


def _engine_from_env(variable_name: str):
    database_url = os.environ[variable_name]
    database_name = make_url(database_url).database

    if not database_name or not database_name.startswith("meal85_"):
        pytest.fail(
            f"{variable_name} must point to a disposable database "
            "whose name starts with 'meal85_'."
        )

    return create_engine(database_url)


def _current_revision(connection) -> str:
    return connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar_one()


def _insert_organization(
    connection,
    *,
    organization_type: str,
    registration_number: str,
    contact_email: str,
) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO organizations (
                name,
                type,
                registration_number,
                registration_authority,
                contact_email,
                address_line,
                city
            )
            VALUES (
                :name,
                :organization_type,
                :registration_number,
                NULL,
                :contact_email,
                'Integration Test Road',
                'Colombo'
            )
            RETURNING organization_id
            """
        ),
        {
            "name": f"MEAL-85 {organization_type}",
            "organization_type": organization_type,
            "registration_number": registration_number,
            "contact_email": contact_email,
        },
    ).scalar_one()


def _run_alembic(database_url: str, *arguments: str):
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url

    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_postgresql_enforces_meal85_unique_constraints():
    """Verify actual PostgreSQL NULLS NOT DISTINCT and membership behavior."""
    engine = _engine_from_env("MEAL85_TEST_DATABASE_URL")

    try:
        with engine.connect() as connection:
            with connection.begin():
                assert _current_revision(connection) == MEAL85_REVISION

                server_version = connection.execute(
                    text("SHOW server_version_num")
                ).scalar_one()
                assert int(server_version) >= 150000

                token = uuid.uuid4().hex
                registration_number = f"MEAL85-PG-{token}"

                # The same registration number is allowed for different types.
                restaurant_id = _insert_organization(
                    connection,
                    organization_type="restaurant",
                    registration_number=registration_number,
                    contact_email=f"restaurant-{token}@example.test",
                )

                bakery_id = _insert_organization(
                    connection,
                    organization_type="bakery",
                    registration_number=registration_number,
                    contact_email=f"bakery-{token}@example.test",
                )

                assert restaurant_id != bakery_id

                # NULL authority is treated as equal by NULLS NOT DISTINCT:
                # same type + same number + NULL authority must be rejected.
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        _insert_organization(
                            connection,
                            organization_type="restaurant",
                            registration_number=registration_number,
                            contact_email=f"duplicate-{token}@example.test",
                        )

                # Create one user and link that user to the first organization.
                user_id = connection.execute(
                    text(
                        """
                        INSERT INTO users (
                            first_name,
                            last_name,
                            email,
                            password_hash,
                            role
                        )
                        VALUES (
                            'MEAL85',
                            'Integration',
                            :email,
                            'test-hash',
                            'business_staff'
                        )
                        RETURNING user_id
                        """
                    ),
                    {"email": f"meal85-{token}@example.test"},
                ).scalar_one()

                connection.execute(
                    text(
                        """
                        INSERT INTO organization_memberships (
                            organization_id,
                            user_id,
                            membership_role,
                            member_status
                        )
                        VALUES (
                            :organization_id,
                            :user_id,
                            'owner',
                            'active'
                        )
                        """
                    ),
                    {
                        "organization_id": restaurant_id,
                        "user_id": user_id,
                    },
                )

                # A user cannot be linked to a second organization.
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                """
                                INSERT INTO organization_memberships (
                                    organization_id,
                                    user_id,
                                    membership_role,
                                    member_status
                                )
                                VALUES (
                                    :organization_id,
                                    :user_id,
                                    'owner',
                                    'active'
                                )
                                """
                            ),
                            {
                                "organization_id": bakery_id,
                                "user_id": user_id,
                            },
                        )
    finally:
        engine.dispose()


def test_upgrade_preflight_rejects_existing_duplicate_memberships():
    """Verify upgrade stops before changing the schema when legacy conflicts exist."""
    database_url = os.environ["MEAL85_UPGRADE_TEST_DATABASE_URL"]
    engine = _engine_from_env("MEAL85_UPGRADE_TEST_DATABASE_URL")

    try:
        with engine.connect() as connection:
            assert _current_revision(connection) == PARENT_REVISION

            duplicate_count = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM (
                        SELECT user_id
                        FROM organization_memberships
                        GROUP BY user_id
                        HAVING COUNT(*) > 1
                    ) AS duplicates
                    """
                )
            ).scalar_one()

            assert duplicate_count > 0, (
                "Upgrade test database must contain a user with multiple "
                "organization memberships."
            )

        result = _run_alembic(database_url, "upgrade", "head")
        output = result.stdout + result.stderr

        assert result.returncode != 0
        assert "Cannot upgrade MEAL-85" in output
        assert "multiple organizations" in output

        with engine.connect() as connection:
            assert _current_revision(connection) == PARENT_REVISION

            old_index_exists = connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_indexes
                        WHERE indexname = 'ix_membership_user_id'
                    )
                    """
                )
            ).scalar_one()

            new_constraint_exists = connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'uq_membership_single_org_per_user'
                    )
                    """
                )
            ).scalar_one()

            assert old_index_exists
            assert not new_constraint_exists
    finally:
        engine.dispose()


def test_downgrade_preflight_rejects_duplicate_global_registration_numbers():
    """Verify downgrade preserves the current schema when legacy uniqueness
    cannot be restored.
    """
    database_url = os.environ["MEAL85_TEST_DATABASE_URL"]
    engine = _engine_from_env("MEAL85_TEST_DATABASE_URL")

    try:
        with engine.connect() as connection:
            assert _current_revision(connection) == MEAL85_REVISION

            duplicate_count = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM (
                        SELECT registration_number
                        FROM organizations
                        WHERE registration_number IS NOT NULL
                        GROUP BY registration_number
                        HAVING COUNT(*) > 1
                    ) AS duplicates
                    """
                )
            ).scalar_one()

            assert duplicate_count > 0, (
                "Downgrade test database must contain duplicate registration "
                "numbers across organizations."
            )

        result = _run_alembic(database_url, "downgrade", PARENT_REVISION)
        output = result.stdout + result.stderr

        assert result.returncode != 0
        assert "Cannot downgrade MEAL-85" in output
        assert "global unique registration_number" in output

        with engine.connect() as connection:
            assert _current_revision(connection) == MEAL85_REVISION

            new_index_exists = connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_indexes
                        WHERE indexname = 'uq_organizations_registration_identity'
                    )
                    """
                )
            ).scalar_one()

            new_constraint_exists = connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'uq_membership_single_org_per_user'
                    )
                    """
                )
            ).scalar_one()

            assert new_index_exists
            assert new_constraint_exists
    finally:
        engine.dispose()
