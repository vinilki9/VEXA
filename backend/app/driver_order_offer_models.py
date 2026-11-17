import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Uuid

from app.database import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class DriverOrderOffer(Base):
    """
    История предложений заказов водителям.

    Статусы:
    pending   — ожидается ответ водителя;
    accepted  — водитель принял предложение;
    rejected  — водитель отказался;
    expired   — время ответа истекло;
    cancelled — предложение отменено системой или диспетчером.
    """

    __tablename__ = "driver_order_offers"

    __table_args__ = (
        UniqueConstraint(
            "order_id",
            "driver_user_id",
            name="uq_driver_order_offers_order_driver",
        ),
        CheckConstraint(
            "status IN "
            "('pending', 'accepted', 'rejected', 'expired', 'cancelled')",
            name="driver_order_offers_status_valid",
        ),
        CheckConstraint(
            "response_timeout_seconds > 0",
            name="driver_order_offers_timeout_positive",
        ),
        CheckConstraint(
            "distance_meters IS NULL OR distance_meters >= 0",
            name="driver_order_offers_distance_nonnegative",
        ),
        Index(
            "ix_driver_order_offers_order_status",
            "order_id",
            "status",
        ),
        Index(
            "ix_driver_order_offers_driver_status",
            "driver_user_id",
            "status",
        ),
        Index(
            "ix_driver_order_offers_status_expires",
            "status",
            "expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )

    driver_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("driver_profiles.user_id", ondelete="RESTRICT"),
        nullable=False,
    )

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    response_timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        default=13,
        nullable=False,
    )

    distance_meters: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    offered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )
