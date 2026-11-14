from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.db.models.donation import Donation, DonationStatus
from app.db.models.organization import (
    MemberStatus,
    MembershipRole,
    Organization,
    OrganizationMembership,
    OrganizationType,
    VerificationStatus,
)
from app.db.models.user import AccountStatus, User, UserRole
from app.schemas.donation import DonationBrowseQuery
from app.services.donation_browse_service import (
    DonationBrowseForbiddenError,
    browse_available_donations,
    ensure_verified_ngo_access,
)


NOW = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)


# SQLite test database එක සඳහා පමණක් JSONB support.
@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(element, compiler, **kwargs):
    return "JSON"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")

    User.__table__.create(engine)
    Organization.__table__.create(engine)
    OrganizationMembership.__table__.create(engine)
    Donation.__table__.create(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def create_ngo_account(
    db,
    *,
    role=UserRole.ngo_staff,
    account_status=AccountStatus.active,
    organization_type=OrganizationType.ngo,
    verification_status=VerificationStatus.approved,
    member_status=MemberStatus.active,
    with_membership=True,
):
    user = User(
        user_id=1,
        first_name="Test",
        last_name="User",
        email="ngo@example.com",
        password_hash="test-only-placeholder",
        role=role,
        account_status=account_status,
    )

    organization = Organization(
        organization_id=1,
        name="Test NGO",
        type=organization_type,
        contact_email="organization@example.com",
        address_line="Test address",
        city="Kurunegala",
        verification_status=verification_status,
    )

    db.add_all([user, organization])
    db.flush()

    if with_membership:
        db.add(
            OrganizationMembership(
                membership_id=1,
                organization_id=1,
                user_id=1,
                membership_role=MembershipRole.owner,
                member_status=member_status,
            )
        )

    db.commit()


def create_donation(db, donation_id, **changes):
    # Donations belong to a separate Business account.
    if db.get(User, 2) is None:
        db.add(
            User(
                user_id=2,
                first_name="Business",
                last_name="Owner",
                email="business@example.com",
                password_hash="test-only-placeholder",
                role=UserRole.business_staff,
                account_status=AccountStatus.active,
            )
        )
        db.flush()

    if db.get(Organization, 2) is None:
        db.add(
            Organization(
                organization_id=2,
                name="Test Restaurant",
                type=OrganizationType.restaurant,
                contact_email="restaurant@example.com",
                address_line="Restaurant address",
                city="Colombo",
                verification_status=VerificationStatus.approved,
            )
        )
        db.flush()

        db.add(
            OrganizationMembership(
                membership_id=2,
                organization_id=2,
                user_id=2,
                membership_role=MembershipRole.owner,
                member_status=MemberStatus.active,
            )
        )
        db.flush()

    values = {
        "donation_id": donation_id,
        "organization_id": 2,
        "created_by_user_id": 2,
        "title": f"Donation {donation_id}",
        "category": "prepared_meal",
        "description": "Test food",
        "total_quantity": Decimal("10.00"),
        "allocated_quantity": Decimal("0.00"),
        "quantity_unit": "portions",
        "available_from": NOW - timedelta(hours=1),
        "pickup_deadline": NOW + timedelta(hours=1),
        "pickup_address": "Restaurant address",
        "pickup_city": "Colombo",
        "status": DonationStatus.available,
        "created_at": NOW - timedelta(hours=2),
    }

    values.update(changes)
    db.add(Donation(**values))
    db.commit()


def browse(db, **filters):
    return browse_available_donations(
        db,
        authenticated_user_id=1,
        filters=DonationBrowseQuery(**filters),
        now=NOW,
    )


def test_approved_ngo_with_active_membership_is_allowed(db):
    create_ngo_account(db)

    assert ensure_verified_ngo_access(
        db,
        authenticated_user_id=1,
    ) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"verification_status": VerificationStatus.pending},
        {"verification_status": VerificationStatus.rejected},
        {"verification_status": VerificationStatus.suspended},
        {"account_status": AccountStatus.disabled},
        {"account_status": AccountStatus.suspended},
        {"member_status": MemberStatus.invited},
        {"member_status": MemberStatus.removed},
        {"role": UserRole.business_staff},
        {"role": UserRole.volunteer},
        {"organization_type": OrganizationType.restaurant},
        {"with_membership": False},
    ],
)
def test_unqualified_account_is_forbidden(db, changes):
    create_ngo_account(db, **changes)

    with pytest.raises(DonationBrowseForbiddenError) as error:
        ensure_verified_ngo_access(
            db,
            authenticated_user_id=1,
        )

    assert error.value.code == "FORBIDDEN"


def test_unknown_user_is_forbidden(db):
    create_ngo_account(db)

    with pytest.raises(DonationBrowseForbiddenError):
        ensure_verified_ngo_access(
            db,
            authenticated_user_id=999,
        )


def test_available_donation_is_returned(db):
    create_ngo_account(db)
    create_donation(db, 1)

    result = browse(db)

    assert [item.donation_id for item in result.data] == [1]
    assert result.data[0].remaining_quantity == Decimal("10.00")
    assert result.pagination.total_items == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"status": DonationStatus.draft},
        {"status": DonationStatus.expired},
        {"status": DonationStatus.cancelled},
        {"status": DonationStatus.fully_allocated},
        {"status": DonationStatus.collected},
        {"pickup_deadline": NOW},
        {"pickup_deadline": NOW - timedelta(minutes=1)},
        {"available_from": NOW + timedelta(minutes=1)},
        {"allocated_quantity": Decimal("10.00")},
    ],
)
def test_unrequestable_donation_is_excluded(db, changes):
    create_ngo_account(db)
    create_donation(db, 1, **changes)

    result = browse(db)

    assert result.data == []
    assert result.pagination.total_items == 0


def test_remaining_quantity_filter(db):
    create_ngo_account(db)

    create_donation(
        db,
        1,
        status=DonationStatus.partially_allocated,
        allocated_quantity=Decimal("6.00"),
    )

    assert browse(db, min_quantity="5.00").data == []

    result = browse(db, min_quantity="4.00")

    assert [item.donation_id for item in result.data] == [1]
    assert result.data[0].remaining_quantity == Decimal("4.00")


def test_city_and_category_filters_ignore_case(db):
    create_ngo_account(db)
    create_donation(db, 1)

    result = browse(
        db,
        city=" colombo ",
        category="PREPARED_MEAL",
    )

    assert [item.donation_id for item in result.data] == [1]
    assert browse(db, city="Kandy").data == []


def test_pagination_and_deadline_sorting(db):
    create_ngo_account(db)

    for donation_id in range(1, 4):
        create_donation(
            db,
            donation_id,
            pickup_deadline=NOW + timedelta(hours=donation_id),
        )

    result = browse(
        db,
        sort="-pickup_deadline",
        page=2,
        page_size=2,
    )

    assert [item.donation_id for item in result.data] == [1]
    assert result.pagination.total_items == 3
    assert result.pagination.total_pages == 2


def test_ngo_can_browse_another_organizations_donation(db):
    create_ngo_account(db)
    create_donation(db, 1)

    result = browse(db)

    assert len(result.data) == 1
    assert result.data[0].organization_id == 2
    assert db.get(Organization, 1).type == OrganizationType.ngo
    assert db.get(Organization, 2).type == OrganizationType.restaurant