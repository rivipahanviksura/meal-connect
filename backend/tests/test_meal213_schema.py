
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

import app.db.models
from app.db.base import Base


def test_organization_documents_registered():
    table = Base.metadata.tables["organization_documents"]

    required_columns = {
        "document_id",
        "organization_id",
        "uploaded_by_user_id",
        "document_type",
        "storage_key",
        "original_filename",
        "content_type",
        "file_size_bytes",
        "review_status",
        "uploaded_at",
        "reviewed_at",
    }

    assert required_columns.issubset(table.columns.keys())


def test_single_account_per_organization_constraint():
    table = Base.metadata.tables["organization_memberships"]

    constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert any(
        constraint.name == "uq_membership_single_account_per_org"
        and {column.name for column in constraint.columns}
        == {"organization_id"}
        for constraint in constraints
    )


def test_organization_operational_details_jsonb():
    table = Base.metadata.tables["organizations"]

    column = table.columns["operational_details"]

    assert isinstance(column.type, JSONB)

    verification_table = Base.metadata.tables[
        "organization_verifications"
    ]

    assert "operational_details" not in verification_table.columns


def test_pickup_pin_and_handover_columns():
    table = Base.metadata.tables["pickups"]

    required_columns = {
        "pin_verifier",
        "pin_expires_at",
        "pin_failed_attempts",
        "pin_locked_until",
        "pin_verified_at",
        "pin_generation",
        "handover_confirmed_by_user_id",
        "handover_confirmed_at",
    }

    assert required_columns.issubset(table.columns.keys())


def test_pickup_pin_check_constraints():
    table = Base.metadata.tables["pickups"]

    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert {
        "ck_pickup_pin_failed_attempts",
        "ck_pickup_pin_generation",
    }.issubset(check_names)


def test_document_storage_key_is_unique():
    table = Base.metadata.tables["organization_documents"]

    assert table.columns["storage_key"].unique is True
