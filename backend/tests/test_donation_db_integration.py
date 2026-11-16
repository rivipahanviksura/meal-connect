
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exception_handlers import APIException
from app.db.session import get_engine
from app.db.models.user import User, UserRole, AccountStatus
from app.db.models.organization import (
    Organization,
    OrganizationType,
    VerificationStatus,
)
from app.db.models.donation import Donation, DonationStatus
from app.schemas.donation import DonationUpdate
from app.services.donation import edit_donation, cancel_donation


def test_real_database_donation_ownership():
    # Never run this test against the main database.
    assert settings.database_url is not None

    db_url = make_url(
        settings.database_url.get_secret_value()
    )

    assert db_url.database == "meal_connect_test"

    engine = get_engine()

    try:
        with engine.connect() as connection:
            # Keep all test changes inside an outer transaction.
            outer_transaction = connection.begin()

            db = Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
            )

            try:
                unique_id = uuid4().hex[:12]
                now = datetime.now(timezone.utc)

                # Create a test business user.
                user = User(
                    first_name="Test",
                    last_name="Owner",
                    email=f"owner_{unique_id}@example.com",
                    password_hash="integration-test-only",
                    role=UserRole.business_staff,
                    account_status=AccountStatus.active,
                )

                db.add(user)
                db.flush()

                # Restaurant A owns the donation.
                restaurant_a = Organization(
                    name=f"Test Restaurant A {unique_id}",
                    type=OrganizationType.restaurant,
                    contact_email=f"a_{unique_id}@example.com",
                    address_line="Colombo",
                    city="Colombo",
                    verification_status=VerificationStatus.approved,
                )

                # Restaurant B does not own the donation.
                restaurant_b = Organization(
                    name=f"Test Restaurant B {unique_id}",
                    type=OrganizationType.restaurant,
                    contact_email=f"b_{unique_id}@example.com",
                    address_line="Colombo",
                    city="Colombo",
                    verification_status=VerificationStatus.approved,
                )

                db.add_all([restaurant_a, restaurant_b])
                db.flush()

                donation = Donation(
                    organization_id=restaurant_a.organization_id,
                    created_by_user_id=user.user_id,
                    title="Rice Packets",
                    category="prepared_meal",
                    description="Integration test donation",
                    total_quantity=Decimal("50"),
                    allocated_quantity=Decimal("0"),
                    quantity_unit="portions",
                    available_from=now,
                    pickup_deadline=now + timedelta(hours=3),
                    pickup_address="Colombo",
                    pickup_city="Colombo",
                    status=DonationStatus.draft,
                )

                db.add(donation)
                db.flush()

                donation_id = donation.donation_id

                # Test 1: Restaurant B cannot edit it.
                with pytest.raises(APIException) as error:
                    edit_donation(
                        db=db,
                        donation_id=donation_id,
                        organization_id=restaurant_b.organization_id,
                        data=DonationUpdate(
                            title="Unauthorized Edit"
                        ),
                    )

                assert error.value.status_code == 404

                # Test 2: Restaurant B cannot cancel it.
                with pytest.raises(APIException) as error:
                    cancel_donation(
                        db=db,
                        donation_id=donation_id,
                        organization_id=restaurant_b.organization_id,
                    )

                assert error.value.status_code == 404

                # Test 3: Restaurant A can edit its donation.
                updated = edit_donation(
                    db=db,
                    donation_id=donation_id,
                    organization_id=restaurant_a.organization_id,
                    data=DonationUpdate(
                        title="Updated Rice Packets"
                    ),
                )

                assert updated.title == "Updated Rice Packets"

                # Test 4: Restaurant A can cancel it.
                cancelled = cancel_donation(
                    db=db,
                    donation_id=donation_id,
                    organization_id=restaurant_a.organization_id,
                )

                assert cancelled.status == DonationStatus.cancelled

                print("Real database ownership test passed")

            finally:
                db.close()
                outer_transaction.rollback()

    finally:
        engine.dispose()


from sqlalchemy import text


def test_postgresql_row_lock():
    assert settings.database_url is not None

    db_url = make_url(
        settings.database_url.get_secret_value()
    )
    assert db_url.database == "meal_connect_test"

    engine = get_engine()

    try:
        with engine.connect() as connection:
            transaction = connection.begin()

            try:
                # PostgreSQL advisory locks are used here
                # to verify two independent connections.
                lock_id = 987654321

                connection.execute(
                    text("SELECT pg_advisory_xact_lock(:id)"),
                    {"id": lock_id},
                )

                with engine.connect() as second_connection:
                    result = second_connection.execute(
                        text("SELECT pg_try_advisory_xact_lock(:id)"),
                        {"id": lock_id},
                    ).scalar()

                    assert result is False

            finally:
                transaction.rollback()

    finally:
        engine.dispose()
