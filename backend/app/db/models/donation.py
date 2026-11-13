
import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DonationStatus(str, enum.Enum):
    draft = "draft"
    available = "available"
    partially_allocated = "partially_allocated"
    fully_allocated = "fully_allocated"
    collected = "collected"
    expired = "expired"
    cancelled = "cancelled"


class Donation(Base):
    __tablename__ = "donations"

    __table_args__ = (
        CheckConstraint(
            "total_quantity > 0",
            name="ck_donation_positive_total",
        ),
        CheckConstraint(
            "allocated_quantity >= 0 AND "
            "allocated_quantity <= total_quantity",
            name="ck_donation_allocation_bounds",
        ),
        CheckConstraint(
            "pickup_deadline > available_from",
            name="ck_donation_deadline",
        ),
        CheckConstraint(
            "prepared_at IS NULL OR "
            "prepared_at <= pickup_deadline",
            name="ck_donation_prepared_at",
        ),
        Index(
            "ix_donations_org_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_donations_status_deadline",
            "status",
            "pickup_deadline",
        ),
    )

    donation_id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )

    organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organizations.organization_id"),
        nullable=False,
    )

    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(180), nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    description: Mapped[str | None] = mapped_column(Text)

    total_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    allocated_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0",
    )

    quantity_unit: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    allergen_info: Mapped[str | None] = mapped_column(Text)

    storage_instructions: Mapped[str | None] = mapped_column(Text)

    prepared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    available_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    pickup_deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    pickup_address: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    pickup_city: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    status: Mapped[DonationStatus] = mapped_column(
        Enum(DonationStatus, name="donation_status"),
        nullable=False,
        server_default="draft",
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
