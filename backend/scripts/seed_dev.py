
"""Development-only fictional seed data for Meal Connect."""

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text

from app.db.session import get_session_factory
from app.db.models.user import User, UserRole, AccountStatus
from app.db.models.organization import (
    Organization,
    OrganizationType,
    VerificationStatus,
    OrganizationMembership,
    MembershipRole,
    MemberStatus,
)
from app.db.models.donation import Donation, DonationStatus


DEMO_EMAILS = {
    "donor": "donor@mealconnect.example.test",
    "ngo": "ngo@mealconnect.example.test",
}

# Deliberately unusable authentication value.
# Demo users must remain disabled.
DISABLED_PASSWORD_MARKER = "!DISABLED_DEV_SEED_ACCOUNT"


def get_or_create_user(session, email, first_name, role):
    user = session.scalar(
        select(User).where(User.email == email)
    )

    if user is not None:
        if user.account_status != AccountStatus.disabled:
            raise RuntimeError(
                "Refusing to reuse an active demo-email account."
            )
        return user

    user = User(
        first_name=first_name,
        last_name="Demo",
        email=email,
        password_hash=DISABLED_PASSWORD_MARKER,
        role=role,
        account_status=AccountStatus.disabled,
    )
    session.add(user)
    session.flush()
    return user


def get_or_create_organization(
    session, registration_number, name, org_type
):
    org = session.scalar(
        select(Organization).where(
            Organization.registration_number
            == registration_number
        )
    )

    if org is not None:
        return org

    org = Organization(
        name=name,
        type=org_type,
        registration_number=registration_number,
        contact_email="contact@mealconnect.example.test",
        address_line="123 Fictional Demo Road",
        city="Demo City",
        district="Demo District",
        verification_status=VerificationStatus.approved,
    )
    session.add(org)
    session.flush()
    return org


def ensure_membership(session, org, user, role):
    existing = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id
            == org.organization_id,
            OrganizationMembership.user_id
            == user.user_id,
        )
    )

    if existing is None:
        session.add(
            OrganizationMembership(
                organization_id=org.organization_id,
                user_id=user.user_id,
                membership_role=role,
                member_status=MemberStatus.active,
            )
        )


def ensure_donation(session, org, donor):
    title = "DEMO - Sample Surplus Food"

    existing = session.scalar(
        select(Donation).where(
            Donation.organization_id == org.organization_id,
            Donation.title == title,
        )
    )

    if existing is not None:
        return

    now = datetime.now(timezone.utc)

    session.add(
        Donation(
            organization_id=org.organization_id,
            created_by_user_id=donor.user_id,
            title=title,
            category="Prepared Food",
            description="Fictional development sample only.",
            total_quantity=Decimal("20.00"),
            allocated_quantity=Decimal("0.00"),
            quantity_unit="portions",
            allergen_info="Demo information only",
            storage_instructions="Not real food",
            available_from=now,
            pickup_deadline=now + timedelta(days=7),
            pickup_address="123 Fictional Demo Road",
            pickup_city="Demo City",
            status=DonationStatus.available,
        )
    )


def main():
    if "--confirm-development" not in sys.argv:
        raise SystemExit(
            "Development seed only. Run with "
            "--confirm-development."
        )

    SessionLocal = get_session_factory()

    with SessionLocal() as session:
        database_name = session.execute(
            text("SELECT current_database()")
        ).scalar_one()

        if database_name not in {
            "meal_connect",
            "meal_connect_dev",
            "meal_connect_test",
        }:
            raise RuntimeError(
                "Seeding refused: unexpected database."
            )

        with session.begin_nested():
            donor = get_or_create_user(
                session,
                DEMO_EMAILS["donor"],
                "Donor",
                UserRole.business_staff,
            )

            ngo_user = get_or_create_user(
                session,
                DEMO_EMAILS["ngo"],
                "NGO",
                UserRole.ngo_staff,
            )

            restaurant = get_or_create_organization(
                session,
                "DEMO-RESTAURANT-001",
                "Meal Connect Demo Restaurant",
                OrganizationType.restaurant,
            )

            ngo = get_or_create_organization(
                session,
                "DEMO-NGO-001",
                "Meal Connect Demo NGO",
                OrganizationType.ngo,
            )

            ensure_membership(
                session, restaurant, donor,
                MembershipRole.owner,
            )

            ensure_membership(
                session, ngo, ngo_user,
                MembershipRole.coordinator,
            )

            ensure_donation(session, restaurant, donor)

        session.commit()

    print("Development seed completed successfully.")


if __name__ == "__main__":
    main()
