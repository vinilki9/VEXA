
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Text,
    Float,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def now_utc():
    return datetime.now(timezone.utc)


class Dispatcher(Base):
    __tablename__ = "dispatchers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(
        String(80), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[str] = mapped_column(
        String(30), default="dispatcher", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class Order(Base):
    __tablename__ = "orders"

    __table_args__ = (
        UniqueConstraint(
            "city_id",
            "idempotency_key",
            name="uq_orders_city_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    city_id: Mapped[str] = mapped_column(
        String(80), index=True, default="obolensk", nullable=False
    )

    customer_name: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    customer_phone: Mapped[str] = mapped_column(String(40), nullable=False)

    anonymous: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    pickup_address: Mapped[str] = mapped_column(String(500), nullable=False)
    destination_address: Mapped[str] = mapped_column(String(500), nullable=False)

    pickup_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    pickup_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(
        String(40), default="new", index=True, nullable=False
    )

    payment_method: Mapped[str] = mapped_column(
        String(30), default="cash", nullable=False
    )

    price_rub: Mapped[int | None] = mapped_column(Integer, nullable=True)

    driver_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    idempotency_key: Mapped[str] = mapped_column(
        String(128), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
    )
