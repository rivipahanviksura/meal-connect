"""Store private document contents and immutable application submissions."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "e721c958e76a"
down_revision = "66af9d4181e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_document_contents",
        sa.Column("document_id", sa.BigInteger(), sa.ForeignKey("organization_documents.document_id"), primary_key=True),
        sa.Column("content", sa.LargeBinary(), nullable=False),
    )
    op.create_table(
        "organization_application_submissions",
        sa.Column("submission_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("organization_id", sa.BigInteger(), sa.ForeignKey("organizations.organization_id"), nullable=False),
        sa.Column("submitted_by_user_id", sa.BigInteger(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_application_submissions_org_id", "organization_application_submissions", ["organization_id"]
    )


def downgrade() -> None:
    op.drop_table("organization_application_submissions")
    op.drop_table("organization_document_contents")
