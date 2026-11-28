
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DistributionRecord(Base):
    __tablename__ = "distribution_records"

    __table_args__ = (
        CheckConstraint(
            "distributed_quantity > 0",
            name="ck_distribution_quantity",
        ),
        CheckConstraint(
            "beneficiary_count >= 0",
            name="ck_beneficiary_count",
        ),
    )

    distribution_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    pickup_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("pickups.pickup_id"),
        nullable=False,
        unique=True,
    )

    recorded_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    distributed_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    beneficiary_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    distributed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
