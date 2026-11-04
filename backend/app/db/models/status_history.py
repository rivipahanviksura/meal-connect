
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StatusHistory(Base):
    __tablename__ = "status_history"

    __table_args__ = (
        Index(
            "ix_status_history_entity",
            "entity_type",
            "entity_id",
            "changed_at",
        ),
    )

    status_history_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    entity_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    old_status: Mapped[str | None] = mapped_column(
        String(50),
    )

    new_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    changed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id"),
    )

    change_reason: Mapped[str | None] = mapped_column(
        Text,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
