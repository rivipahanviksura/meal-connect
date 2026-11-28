
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
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
    fulfilled = "fulfilled"


class DonationRequest(Base):
    __tablename__ = "donation_requests"

    __table_args__ = (
        CheckConstraint(
            "requested_quantity > 0",
            name="ck_request_quantity",
        ),
        Index(
            "ix_requests_donation_status",
            "donation_id",
            "status",
        ),
        Index(
            "ix_requests_ngo_status",
            "ngo_organization_id",
            "status",
        ),
    )

    request_id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )

    donation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("donations.donation_id"),
        nullable=False,
    )

    ngo_organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organizations.organization_id"),
        nullable=False,
    )

    requested_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    requested_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"),
        nullable=False,
        server_default="pending",
    )

    request_note: Mapped[str | None] = mapped_column(Text)

    decision_note: Mapped[str | None] = mapped_column(Text)

    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id"),
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
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
