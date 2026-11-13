from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

def now_utc():
    return datetime.now(timezone.utc)

class Dispatcher(Base):
    __tablename__ = "dispatchers"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    role: Mapped[str] = mapped_column(String(30), default="dispatcher")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[str] = mapped_column(String(80), index=True, default="obolensk")
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_phone: Mapped[str] = mapped_column(String(40))
    pickup_address: Mapped[str] = mapped_column(String(500))
    destination_address: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(40), default="new", index=True)
    payment_method: Mapped[str] = mapped_column(String(30), default="cash")
    price_rub: Mapped[int | None] = mapped_column(Integer, nullable=True)
    driver_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
