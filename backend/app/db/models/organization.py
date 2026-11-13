
import enum
from sqlalchemy.dialects.postgresql import JSONB
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    Date,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrganizationType(str, enum.Enum):
    restaurant = "restaurant"
    bakery = "bakery"
    ngo = "ngo"


class VerificationStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    suspended = "suspended"


class MembershipRole(str, enum.Enum):
    owner = "owner"
    manager = "manager"
    staff = "staff"
    coordinator = "coordinator"
    collector = "collector"


class MemberStatus(str, enum.Enum):
    invited = "invited"
    active = "active"
    removed = "removed"


class Organization(Base):
    __tablename__ = "organizations"

    organization_id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(180), nullable=False
    )

    type: Mapped[OrganizationType] = mapped_column(
        Enum(OrganizationType, name="organization_type"),
        nullable=False,
    )

    registration_number: Mapped[str | None] = mapped_column(
        String(100), unique=True
    )

    contact_email: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    contact_phone: Mapped[str | None] = mapped_column(
        String(25)
    )

    address_line: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    city: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    district: Mapped[str | None] = mapped_column(
        String(120)
    )

    registration_authority: Mapped[str | None] = mapped_column(
        String(180), nullable=True
    )

    registration_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    registration_expiry_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    representative_name: Mapped[str | None] = mapped_column(
        String(180), nullable=True
    )

    representative_designation: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    pickup_location: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    operational_details: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"),
        nullable=False,
        server_default="pending",
    )

    verified_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.user_id")
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    operational_details: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_membership_org_user",
        ),
        UniqueConstraint(
            "organization_id",
            name="uq_membership_single_account_per_org",
        ),
        Index("ix_membership_user_id", "user_id"),
    )

    membership_id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )

    organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organizations.organization_id"),
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    membership_role: Mapped[MembershipRole] = mapped_column(
        Enum(MembershipRole, name="membership_role"),
        nullable=False,
        server_default="staff",
    )

    member_status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus, name="member_status"),
        nullable=False,
        server_default="active",
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class OrganizationVerification(Base):
    __tablename__ = "organization_verifications"

    verification_id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )

    organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organizations.organization_id"),
        nullable=False,
    )

    reviewed_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    decision: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"),
        nullable=False,
    )

    review_note: Mapped[str | None] = mapped_column(
        Text
    )

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
