
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

import pytest

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_engine
from app.db.models.user import User, UserRole, AccountStatus
from app.db.models.organization import (
    Organization,
    OrganizationType,
    VerificationStatus,
)
from app.services.donation_lifecycle import (
    Donation,
    DonationStatus,
    StatusHistory,
    APIException,
    publish_donation,
)

from app.schemas.donation import DonationBrowseQuery
from app.services.donation_browse_service import (
    browse_available_donations,
)

@pytest.fixture
def postgres_publish_db():
    assert settings.database_url is not None

    db_url = make_url(
        settings.database_url.get_secret_value()
    )

    # Safety: never execute against the main database.
    assert db_url.database == "meal_connect_test"

    engine = get_engine()

    try:
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            assert database_name == "meal_connect_test"

            connection.rollback()

            outer_transaction = connection.begin()

            db = Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
            )

            try:
                yield db
            finally:
                db.close()

                if outer_transaction.is_active:
                    outer_transaction.rollback()

    finally:
        engine.dispose()


@pytest.fixture
def publish_test_data(postgres_publish_db):
    db = postgres_publish_db
    unique_id = uuid4().hex[:12]
    now = datetime.now(timezone.utc)

    user = User(
        first_name="Publish",
        last_name="QA",
        email=f"publish_{unique_id}@example.com",
        password_hash="integration-test-only",
        role=UserRole.business_staff,
        account_status=AccountStatus.active,
    )

    db.add(user)
    db.flush()

    restaurant_a = Organization(
        name=f"Publish Restaurant A {unique_id}",
        type=OrganizationType.restaurant,
        contact_email=f"a_{unique_id}@example.com",
        address_line="Colombo",
        city="Colombo",
        verification_status=VerificationStatus.approved,
    )

    restaurant_b = Organization(
        name=f"Publish Restaurant B {unique_id}",
        type=OrganizationType.restaurant,
        contact_email=f"b_{unique_id}@example.com",
        address_line="Galle",
        city="Galle",
        verification_status=VerificationStatus.approved,
    )

    db.add_all([restaurant_a, restaurant_b])
    db.flush()

    donation = Donation(
        organization_id=restaurant_a.organization_id,
        created_by_user_id=user.user_id,
        title="MEAL-226 Rice Packets",
        category="prepared_meal",
        description="Publish integration test",
        total_quantity=Decimal("50"),
        allocated_quantity=Decimal("0"),
        quantity_unit="portions",
        available_from=now - timedelta(minutes=10),
        pickup_deadline=now + timedelta(hours=3),
        pickup_address="Colombo",
        pickup_city="Colombo",
        status=DonationStatus.draft,
    )

    db.add(donation)
    db.flush()

    data = {
        "donation_id": donation.donation_id,
        "owner_id": restaurant_a.organization_id,
        "other_id": restaurant_b.organization_id,
        "user_id": user.user_id,
    }

    db.commit()

    return data


def get_publish_history(db, donation_id):
    return db.scalars(
        select(StatusHistory).where(
            StatusHistory.entity_type == "donation",
            StatusHistory.entity_id == donation_id,
            StatusHistory.new_status == "available",
        )
    ).all()


# DB-01 / DB-02:
# Verify donation status and audit history persistence.
def test_postgres_publish_persistence(
    postgres_publish_db,
    publish_test_data,
):
    db = postgres_publish_db
    data = publish_test_data

    publish_donation(
        db=db,
        donation_id=data["donation_id"],
        organization_id=data["owner_id"],
        user_id=data["user_id"],
    )

    db.expire_all()

    persisted = db.get(
        Donation, data["donation_id"]
    )

    assert persisted.status == DonationStatus.available
    assert persisted.total_quantity == Decimal("50")
    assert persisted.allocated_quantity == Decimal("0")

    history = get_publish_history(
        db, data["donation_id"]
    )

    assert len(history) == 1
    assert history[0].old_status == "draft"
    assert history[0].new_status == "available"
    assert (
        history[0].changed_by_user_id
        == data["user_id"]
    )


# DB-03:
# Another organization cannot publish the donation.
def test_postgres_publish_ownership(
    postgres_publish_db,
    publish_test_data,
):
    db = postgres_publish_db
    data = publish_test_data

    with pytest.raises(APIException) as exc:
        publish_donation(
            db=db,
            donation_id=data["donation_id"],
            organization_id=data["other_id"],
            user_id=data["user_id"],
        )

    assert exc.value.status_code == 404

    db.expire_all()

    persisted = db.get(
        Donation, data["donation_id"]
    )

    assert persisted.status == DonationStatus.draft

    assert get_publish_history(
        db, data["donation_id"]
    ) == []


# DB-04:
# Expired drafts must remain unchanged.
def test_postgres_publish_expired_draft(
    postgres_publish_db,
    publish_test_data,
):
    db = postgres_publish_db
    data = publish_test_data

    donation = db.get(
        Donation, data["donation_id"]
    )

    now = datetime.now(timezone.utc)

    donation.available_from = now - timedelta(hours=3)
    donation.pickup_deadline = now - timedelta(hours=1)

    db.commit()

    with pytest.raises(APIException) as exc:
        publish_donation(
            db=db,
            donation_id=data["donation_id"],
            organization_id=data["owner_id"],
            user_id=data["user_id"],
        )

    assert exc.value.status_code == 409

    db.expire_all()

    persisted = db.get(
        Donation, data["donation_id"]
    )

    assert persisted.status == DonationStatus.draft

    assert get_publish_history(
        db, data["donation_id"]
    ) == []


# DB-05:
# Flush changes into PostgreSQL, simulate failure
# before commit, and verify both changes roll back.
def test_postgres_publish_atomic_rollback(
    postgres_publish_db,
    publish_test_data,
):
    db = postgres_publish_db
    data = publish_test_data

    def failing_commit():
        db.flush()
        raise RuntimeError("Simulated transaction failure")

    with patch.object(
        db,
        "commit",
        side_effect=failing_commit,
    ):
        with pytest.raises(
            RuntimeError,
            match="Simulated transaction failure",
        ):
            publish_donation(
                db=db,
                donation_id=data["donation_id"],
                organization_id=data["owner_id"],
                user_id=data["user_id"],
            )

    db.expire_all()

    persisted = db.get(
        Donation, data["donation_id"]
    )

    assert persisted.status == DonationStatus.draft

    assert get_publish_history(
        db, data["donation_id"]
    ) == []


# Repeated publishing must not create duplicate history.
def test_postgres_publish_twice_rejected(
    postgres_publish_db,
    publish_test_data,
):
    db = postgres_publish_db
    data = publish_test_data

    publish_donation(
        db=db,
        donation_id=data["donation_id"],
        organization_id=data["owner_id"],
        user_id=data["user_id"],
    )

    with pytest.raises(APIException) as exc:
        publish_donation(
            db=db,
            donation_id=data["donation_id"],
            organization_id=data["owner_id"],
            user_id=data["user_id"],
        )

    assert exc.value.status_code == 409

    persisted = db.get(
        Donation, data["donation_id"]
    )

    assert persisted.status == DonationStatus.available

    assert len(
        get_publish_history(db, data["donation_id"])
    ) == 1


def donation_is_visible(db, donation_id, now):
    page = 1

    while True:
        response = browse_available_donations(
            db=db,
            filters=DonationBrowseQuery(
                page=page,
                page_size=100,
            ),
            now=now,
        )

        if any(
            item.donation_id == donation_id
            for item in response.data
        ):
            return True

        if page >= response.pagination.total_pages:
            return False

        page += 1


# DB-06: Draft donations must remain hidden.
def test_postgres_draft_hidden_from_ngo_discovery(
    postgres_publish_db,
    publish_test_data,
):
    db = postgres_publish_db
    data = publish_test_data

    assert not donation_is_visible(
        db,
        data["donation_id"],
        datetime.now(timezone.utc),
    )


# DB-07: Published donations become visible.
def test_postgres_published_donation_visible_to_ngo(
    postgres_publish_db,
    publish_test_data,
):
    db = postgres_publish_db
    data = publish_test_data

    # Confirm that the draft is hidden before publishing.
    assert not donation_is_visible(
        db,
        data["donation_id"],
        datetime.now(timezone.utc),
    )

    publish_donation(
        db=db,
        donation_id=data["donation_id"],
        organization_id=data["owner_id"],
        user_id=data["user_id"],
    )

    db.expire_all()

    # Confirm that the published donation is visible.
    assert donation_is_visible(
        db,
        data["donation_id"],
        datetime.now(timezone.utc),
    )


# DB-08: Future availability must be respected.
def test_postgres_future_published_donation_visibility(
    postgres_publish_db,
    publish_test_data,
):
    db = postgres_publish_db
    data = publish_test_data

    donation = db.get(
        Donation, data["donation_id"]
    )

    now = datetime.now(timezone.utc)
    available_from = now + timedelta(hours=1)
    pickup_deadline = now + timedelta(hours=3)

    donation.available_from = available_from
    donation.pickup_deadline = pickup_deadline

    db.commit()

    published = publish_donation(
        db=db,
        donation_id=data["donation_id"],
        organization_id=data["owner_id"],
        user_id=data["user_id"],
    )

    assert published.status == DonationStatus.available

    # Hidden before the availability window.
    assert not donation_is_visible(
        db,
        data["donation_id"],
        now,
    )

    # Visible when the availability window opens.
    assert donation_is_visible(
        db,
        data["donation_id"],
        available_from,
    )

    # Hidden when the pickup deadline is reached.
    assert not donation_is_visible(
        db,
        data["donation_id"],
        pickup_deadline,
    )
