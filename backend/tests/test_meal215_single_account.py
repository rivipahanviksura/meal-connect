from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.organization import (
    MemberStatus,
    MembershipRole,
    Organization,
    OrganizationMembership,
    OrganizationType,
    VerificationStatus,
)
from app.db.models.user import AccountStatus, User, UserRole
from app.db.session import get_engine


@pytest.mark.parametrize(
    "membership_status",
    [MemberStatus.invited, MemberStatus.active, MemberStatus.removed],
)
def test_organization_cannot_have_second_account(membership_status):
    assert settings.database_url is not None
    url = make_url(settings.database_url.get_secret_value())

    assert url.get_backend_name() == "postgresql"
    assert url.database == "meal_connect_test"
    assert url.host in {"localhost", "127.0.0.1", "::1"}

    engine = get_engine()

    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT current_database()")
            ).scalar_one() == "meal_connect_test"

            connection.rollback()
            outer = connection.begin()

            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    unique = uuid4().hex

                    users = [
                        User(
                            first_name="QA",
                            last_name=f"Owner {index}",
                            email=f"single-owner-{unique}-{index}@example.com",
                            password_hash="fixture-only-not-a-login-account",
                            role=UserRole.business_staff,
                            account_status=AccountStatus.active,
                        )
                        for index in range(2)
                    ]

                    organization = Organization(
                        name=f"QA single account {unique}",
                        type=OrganizationType.restaurant,
                        contact_email=f"organization-{unique}@example.com",
                        address_line="QA Test Road",
                        city="Kurunegala",
                        verification_status=VerificationStatus.pending,
                    )

                    db.add_all([*users, organization])
                    db.flush()

                    db.add(
                        OrganizationMembership(
                            organization_id=organization.organization_id,
                            user_id=users[0].user_id,
                            membership_role=MembershipRole.owner,
                            member_status=membership_status,
                        )
                    )
                    db.flush()

                    with pytest.raises(IntegrityError) as caught:
                        with db.begin_nested():
                            db.add(
                                OrganizationMembership(
                                    organization_id=organization.organization_id,
                                    user_id=users[1].user_id,
                                    membership_role=MembershipRole.owner,
                                    member_status=MemberStatus.active,
                                )
                            )
                            db.flush()

                    assert caught.value.orig.diag.constraint_name == (
                        "uq_membership_single_account_per_org"
                    )

                    count = db.scalar(
                        text(
                            "SELECT COUNT(*) FROM organization_memberships "
                            "WHERE organization_id = :organization_id"
                        ),
                        {"organization_id": organization.organization_id},
                    )
                    assert count == 1
            finally:
                outer.rollback()
    finally:
        engine.dispose()