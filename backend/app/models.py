
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


# ------------------------------------------------------------
# USER ROLES
# ------------------------------------------------------------

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id",
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("role", String(30), primary_key=True),
)


# ------------------------------------------------------------
# CITIES AND BRANCHES
# ------------------------------------------------------------

class City(Base):
    __tablename__ = "cities"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    code: Mapped[str] = mapped_column(
        String(80), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )

class CityOrderCounter(Base):
    __tablename__ = "city_order_counters"

    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id", ondelete="CASCADE"),
        primary_key=True,
    )

    last_number: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
    )


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cities.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )




class CitySetting(Base):
    __tablename__ = "city_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cities.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_price_kopecks: Mapped[int] = mapped_column(Integer, default=0)
    price_per_km_kopecks: Mapped[int] = mapped_column(Integer, default=0)
    price_per_minute_kopecks: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


# ------------------------------------------------------------
# USERS AND PROFILES
# ------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    phone: Mapped[str | None] = mapped_column(
        String(40), unique=True, index=True
    )
    username: Mapped[str | None] = mapped_column(
        String(80), unique=True, index=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    phone_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
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


class PassengerProfile(Base):
    __tablename__ = "passenger_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    full_name: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class DriverProfile(Base):
    __tablename__ = "driver_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cities.id"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("branches.id")
    )
    rating: Mapped[float] = mapped_column(
        Numeric(3, 2), default=5.00, nullable=False
    )
    commission_rate: Mapped[float] = mapped_column(
        Numeric(5, 2), default=10.00, nullable=False
    )
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class DispatcherProfile(Base):
    __tablename__ = "dispatcher_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("branches.id")
    )
    role: Mapped[str] = mapped_column(
        String(30), default="dispatcher", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


# ------------------------------------------------------------
# VEHICLES AND DOCUMENTS
# ------------------------------------------------------------

class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    driver_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("driver_profiles.user_id"),
        nullable=False,
        index=True,
    )
    brand: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str] = mapped_column(String(50), nullable=False)
    plate_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    vehicle_class: Mapped[str] = mapped_column(
        String(40), default="standard"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class DriverDocument(Base):
    __tablename__ = "driver_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    driver_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("driver_profiles.user_id"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(60), nullable=False)
    file_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


# ------------------------------------------------------------
# ORDERS
# ------------------------------------------------------------

class Order(Base):
    __tablename__ = "orders"

    __table_args__ = (
        UniqueConstraint(
            "city_id",
            "idempotency_key",
            name="uq_orders_city_idempotency",
        ),
        UniqueConstraint("public_number", name="uq_orders_public_number"),
        CheckConstraint(
            "price_rub IS NULL OR price_rub >= 0",
            name="orders_price_rub_nonnegative",
        ),
        CheckConstraint(
            "price_kopecks IS NULL OR price_kopecks >= 0",
            name="orders_price_kopecks_nonnegative",
        ),
        Index("ix_orders_city_status_created", "city_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    public_number: Mapped[str] = mapped_column(
        String(40), nullable=False
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cities.id"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("branches.id"),
        nullable=True,
        index=True,
    )
    passenger_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("passenger_profiles.user_id")
    )
    driver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("driver_profiles.user_id"), index=True
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("vehicles.id")
    )

    # Existing client order fields
    customer_name: Mapped[str | None] = mapped_column(String(120))
    customer_phone: Mapped[str] = mapped_column(String(40), nullable=False)
    anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    pickup_address: Mapped[str] = mapped_column(String(500), nullable=False)
    destination_address: Mapped[str] = mapped_column(String(500), nullable=False)

    pickup_latitude: Mapped[float | None] = mapped_column(Float)
    pickup_longitude: Mapped[float | None] = mapped_column(Float)
    destination_latitude: Mapped[float | None] = mapped_column(Float)
    destination_longitude: Mapped[float | None] = mapped_column(Float)

    status: Mapped[str] = mapped_column(
        String(40), default="new", nullable=False, index=True
    )
    payment_method: Mapped[str] = mapped_column(
        String(30), default="cash", nullable=False
    )

    # price_rub retained for compatibility during API transition.
    price_rub: Mapped[int | None] = mapped_column(Integer)
    price_kopecks: Mapped[int | None] = mapped_column(Integer)

    comment: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
    )


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    old_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class OrderAssignment(Base):
    __tablename__ = "order_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    driver_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("driver_profiles.user_id"), index=True
    )
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id")
    )
    assignment_type: Mapped[str] = mapped_column(
        String(20), default="auto", nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderPrice(Base):
    __tablename__ = "order_prices"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    base_kopecks: Mapped[int] = mapped_column(Integer, default=0)
    distance_kopecks: Mapped[int] = mapped_column(Integer, default=0)
    time_kopecks: Mapped[int] = mapped_column(Integer, default=0)
    extras_kopecks: Mapped[int] = mapped_column(Integer, default=0)
    anonymous_surcharge_kopecks: Mapped[int] = mapped_column(Integer, default=0)
    total_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    calculation_details: Mapped[dict] = mapped_column(JSON, default=dict)
    confirmed_by_driver_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class CargoOrderDetail(Base):
    __tablename__ = "cargo_order_details"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        primary_key=True,
    )
    cargo_description: Mapped[str | None] = mapped_column(Text)
    cargo_weight_kg: Mapped[float | None] = mapped_column(Float)
    movers_count: Mapped[int] = mapped_column(Integer, default=1)
    floor_from: Mapped[int | None] = mapped_column(Integer)
    floor_to: Mapped[int | None] = mapped_column(Integer)
    has_elevator_from: Mapped[bool | None] = mapped_column(Boolean)
    has_elevator_to: Mapped[bool | None] = mapped_column(Boolean)


# ------------------------------------------------------------
# PAYMENTS AND DRIVER FINANCE
# ------------------------------------------------------------

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )
    external_reference: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    driver_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("driver_profiles.user_id"), nullable=False
    )
    rate_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class DriverTransaction(Base):
    __tablename__ = "driver_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    driver_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("driver_profiles.user_id"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id")
    )
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class DriverPayout(Base):
    __tablename__ = "driver_payouts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    driver_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("driver_profiles.user_id"),
        nullable=False,
        index=True,
    )
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="requested", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ------------------------------------------------------------
# SUPPORT
# ------------------------------------------------------------

class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cities.id"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="open", nullable=False
    )
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id")
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class SupportRating(Base):
    __tablename__ = "support_ratings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("support_tickets.id"),
        unique=True,
        nullable=False,
    )
    operator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id")
    )
    stars: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


# ------------------------------------------------------------
# NOTIFICATIONS AND DEVICES
# ------------------------------------------------------------

class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
