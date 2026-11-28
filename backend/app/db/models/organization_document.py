
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    LargeBinary,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrganizationDocument(Base):
    __tablename__ = "organization_documents"

    __table_args__ = (
        CheckConstraint(
            "file_size_bytes > 0",
            name="ck_org_document_positive_file_size",
        ),
        Index(
            "ix_org_documents_org_id",
            "organization_id",
        ),
    )

    document_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organizations.organization_id"),
        nullable=False,
    )

    uploaded_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    document_type: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    review_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="pending",
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class OrganizationDocumentContent(Base):
    __tablename__ = "organization_document_contents"

    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organization_documents.document_id"), primary_key=True
    )
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class OrganizationApplicationSubmission(Base):
    __tablename__ = "organization_application_submissions"
    __table_args__ = (Index("ix_application_submissions_org_id", "organization_id"),)

    submission_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organizations.organization_id"), nullable=False
    )
    submitted_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id"), nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
