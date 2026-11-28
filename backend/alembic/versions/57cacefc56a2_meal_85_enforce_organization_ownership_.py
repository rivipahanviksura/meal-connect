"""MEAL-85 enforce organization ownership and registration uniqueness.

Revision ID: 57cacefc56a2
Revises: e721c958e76a
Create Date: 2026-11-20 09:19:30.182037
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "57cacefc56a2"
down_revision: Union[str, Sequence[str], None] = "e721c958e76a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _check_upgrade_conflicts() -> None:
    """Detect existing data that would violate the new unique constraints."""
    bind = op.get_bind()

    duplicate_memberships = bind.execute(
        sa.text(
            """
            SELECT user_id, COUNT(*) AS membership_count
            FROM organization_memberships
            GROUP BY user_id
            HAVING COUNT(*) > 1
            ORDER BY user_id
            LIMIT 10
            """
        )
    ).fetchall()

    if duplicate_memberships:
        raise RuntimeError(
            "Cannot upgrade MEAL-85: some users belong to multiple "
            "organizations. Resolve these duplicate memberships first. "
            f"Examples (user_id, count): {duplicate_memberships}"
        )

    duplicate_registration_identities = bind.execute(
        sa.text(
            """
            SELECT type, registration_authority, registration_number,
                   COUNT(*) AS organization_count
            FROM organizations
            WHERE registration_number IS NOT NULL
            GROUP BY type, registration_authority, registration_number
            HAVING COUNT(*) > 1
            ORDER BY registration_number
            LIMIT 10
            """
        )
    ).fetchall()

    if duplicate_registration_identities:
        raise RuntimeError(
            "Cannot upgrade MEAL-85: duplicate organization registration "
            "identities already exist. Resolve these records first. "
            "Examples (type, authority, registration_number, count): "
            f"{duplicate_registration_identities}"
        )


def _check_downgrade_conflicts() -> None:
    """Detect data that would violate the previous global unique constraint."""
    bind = op.get_bind()

    duplicate_registration_numbers = bind.execute(
        sa.text(
            """
            SELECT registration_number, COUNT(*) AS organization_count
            FROM organizations
            WHERE registration_number IS NOT NULL
            GROUP BY registration_number
            HAVING COUNT(*) > 1
            ORDER BY registration_number
            LIMIT 10
            """
        )
    ).fetchall()

    if duplicate_registration_numbers:
        raise RuntimeError(
            "Cannot downgrade MEAL-85: the previous global unique "
            "registration_number constraint cannot be restored because "
            "multiple organizations use the same registration number. "
            "Resolve these records first. "
            f"Examples (registration_number, count): "
            f"{duplicate_registration_numbers}"
        )


def upgrade() -> None:
    """Apply organization ownership and registration identity constraints."""
    # Run all checks before making schema changes.
    _check_upgrade_conflicts()

    op.drop_index(
        op.f("ix_membership_user_id"),
        table_name="organization_memberships",
    )
    op.create_unique_constraint(
        "uq_membership_single_org_per_user",
        "organization_memberships",
        ["user_id"],
    )

    op.drop_constraint(
        op.f("organizations_registration_number_key"),
        "organizations",
        type_="unique",
    )
    op.create_index(
        "uq_organizations_registration_identity",
        "organizations",
        ["type", "registration_authority", "registration_number"],
        unique=True,
        postgresql_where=sa.text("registration_number IS NOT NULL"),
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    """Restore the previous organization constraints."""
    # Check before dropping the current index or changing constraints.
    _check_downgrade_conflicts()

    op.drop_index(
        "uq_organizations_registration_identity",
        table_name="organizations",
        postgresql_where=sa.text("registration_number IS NOT NULL"),
        postgresql_nulls_not_distinct=True,
    )
    op.create_unique_constraint(
        op.f("organizations_registration_number_key"),
        "organizations",
        ["registration_number"],
        postgresql_nulls_not_distinct=False,
    )

    op.drop_constraint(
        "uq_membership_single_org_per_user",
        "organization_memberships",
        type_="unique",
    )
    op.create_index(
        op.f("ix_membership_user_id"),
        "organization_memberships",
        ["user_id"],
        unique=False,
    )
