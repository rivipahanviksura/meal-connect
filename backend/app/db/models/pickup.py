
import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PickupStatus(str, enum.Enum):
    assigned = "assigned"
    scheduled = "scheduled"
    picked_up = "picked_up"
    delivered = "delivered"
    failed = "failed"
    cancelled = "cancelled"


class Pickup(Base):
    __tablename__ = "pickups"

    pickup_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    request_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("donation_requests.request_id"),
        nullable=False,
        unique=True,
    )

    collector_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id"),
        nullable=True,
    )

    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    picked_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    status: Mapped[PickupStatus] = mapped_column(
        Enum(PickupStatus, name="pickup_status"),
        nullable=False,
        server_default="assigned",
    )

    pickup_notes: Mapped[str | None] = mapped_column(Text)

    delivery_notes: Mapped[str | None] = mapped_column(Text)

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
