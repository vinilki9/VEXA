import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Uuid

from app.database import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# CITIES
# ============================================================

class City(Base):
    __tablename__ = "cities"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    code: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )


# ============================================================
# USERS
# Единая учётная запись для разных ролей
# ============================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    username: Mapped[str | None] = mapped_column(
        String(80),
        unique=True,
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(40),
        unique=True,
        nullable=True,
    )

    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )


# ============================================================
# BRANCHES
# ============================================================

class Branch(Base):
    __tablename__ = "branches"

    __table_args__ = (
        UniqueConstraint(
            "city_id",
            "name",
            name="uq_branches_city_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )


# ============================================================
# TARIFFS
# ============================================================

class Tariff(Base):
    __tablename__ = "tariffs"

    __table_args__ = (
        UniqueConstraint(
            "city_id",
            "code",
            name="uq_tariffs_city_code",
        ),
        CheckConstraint(
            "base_price_kopecks >= 0",
            name="tariffs_base_price_nonnegative",
        ),
        CheckConstraint(
            "price_per_km_kopecks >= 0",
            name="tariffs_price_per_km_nonnegative",
        ),
        CheckConstraint(
            "price_per_minute_kopecks >= 0",
            name="tariffs_price_per_minute_nonnegative",
        ),
        CheckConstraint(
            "minimum_fare_kopecks IS NULL OR minimum_fare_kopecks >= 0",
            name="tariffs_minimum_fare_nonnegative",
        ),
        CheckConstraint(
            "maximum_fare_kopecks IS NULL OR maximum_fare_kopecks >= 0",
            name="tariffs_maximum_fare_nonnegative",
        ),
        CheckConstraint(
            """
            minimum_fare_kopecks IS NULL
            OR maximum_fare_kopecks IS NULL
            OR maximum_fare_kopecks >= minimum_fare_kopecks
            """,
            name="tariffs_maximum_fare_gte_minimum",
        ),
        CheckConstraint(
            "child_seat_surcharge_kopecks >= 0",
            name="tariffs_child_seat_surcharge_nonnegative",
        ),
        CheckConstraint(
            "animal_transport_surcharge_kopecks >= 0",
            name="tariffs_animal_surcharge_nonnegative",
        ),
        CheckConstraint(
            "cargo_loader_price_per_person_kopecks >= 0",
            name="tariffs_cargo_loader_price_nonnegative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id"),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    vehicle_class: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    base_price_kopecks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    price_per_km_kopecks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    price_per_minute_kopecks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    minimum_fare_kopecks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    maximum_fare_kopecks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    child_seat_surcharge_kopecks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10_000,
    )

    animal_transport_surcharge_kopecks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10_000,
    )

    cargo_vehicle_surcharges: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    cargo_loader_price_per_person_kopecks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )


# ============================================================
# PASSENGER PROFILES
# ============================================================

class PassengerProfile(Base):
    __tablename__ = "passenger_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        primary_key=True,
    )

    display_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )


# ============================================================
# DRIVER PROFILES
# ============================================================

class DriverProfile(Base):
    __tablename__ = "driver_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        primary_key=True,
    )

    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id"),
        nullable=False,
        index=True,
    )

    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("branches.id"),
        nullable=True,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_online: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("5.00"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )


# ============================================================
# DRIVER LOCATIONS
# Последнее известное местоположение водителя
# ============================================================

class DriverLocation(Base):
    __tablename__ = "driver_locations"

    __table_args__ = (
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="driver_locations_latitude_range",
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="driver_locations_longitude_range",
        ),
        CheckConstraint(
            "accuracy_meters IS NULL OR accuracy_meters >= 0",
            name="driver_locations_accuracy_nonnegative",
        ),
        Index(
            "ix_driver_locations_recorded_at",
            "recorded_at",
        ),
    )

    driver_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "driver_profiles.user_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )

    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    accuracy_meters: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


# ============================================================
# DISPATCHER PROFILES
# ============================================================

class DispatcherProfile(Base):
    __tablename__ = "dispatcher_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        primary_key=True,
    )

    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("branches.id"),
        nullable=True,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(40),
        default="dispatcher",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )


# ============================================================
# VEHICLES
# ============================================================

class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    driver_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("driver_profiles.user_id"),
        nullable=False,
        index=True,
    )

    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id"),
        nullable=False,
        index=True,
    )

    make: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    model: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    color: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    license_plate: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )


# ============================================================
# CITY ORDER COUNTERS
# ============================================================

class CityOrderCounter(Base):
    __tablename__ = "city_order_counters"

    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id"),
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


# ============================================================
# ORDERS
# ============================================================

class Order(Base):
    __tablename__ = "orders"

    __table_args__ = (
        UniqueConstraint(
            "city_id",
            "idempotency_key",
            name="uq_orders_city_idempotency",
        ),
        UniqueConstraint(
            "public_number",
            name="uq_orders_public_number",
        ),
        CheckConstraint(
            "price_rub IS NULL OR price_rub >= 0",
            name="orders_price_rub_nonnegative",
        ),
        CheckConstraint(
            "price_kopecks IS NULL OR price_kopecks >= 0",
            name="orders_price_kopecks_nonnegative",
        ),
        CheckConstraint(
            "cargo_loaders >= 0 AND cargo_loaders <= 4",
            name="orders_cargo_loaders_range",
        ),
        CheckConstraint(
            """
            (
                fare_base_price_kopecks IS NULL
                AND fare_distance_price_kopecks IS NULL
                AND fare_time_price_kopecks IS NULL
                AND fare_limit_adjustment_kopecks IS NULL
                AND anonymous_surcharge_kopecks IS NULL
                AND child_seat_surcharge_kopecks IS NULL
                AND animal_transport_surcharge_kopecks IS NULL
                AND cargo_vehicle_surcharge_kopecks IS NULL
                AND cargo_loaders_surcharge_kopecks IS NULL
            )
            OR
            (
                fare_base_price_kopecks IS NOT NULL
                AND fare_distance_price_kopecks IS NOT NULL
                AND fare_time_price_kopecks IS NOT NULL
                AND fare_limit_adjustment_kopecks IS NOT NULL
                AND anonymous_surcharge_kopecks IS NOT NULL
                AND child_seat_surcharge_kopecks IS NOT NULL
                AND animal_transport_surcharge_kopecks IS NOT NULL
                AND cargo_vehicle_surcharge_kopecks IS NOT NULL
                AND cargo_loaders_surcharge_kopecks IS NOT NULL
                AND price_kopecks IS NOT NULL
                AND fare_base_price_kopecks >= 0
                AND fare_distance_price_kopecks >= 0
                AND fare_time_price_kopecks >= 0
                AND anonymous_surcharge_kopecks >= 0
                AND child_seat_surcharge_kopecks >= 0
                AND animal_transport_surcharge_kopecks >= 0
                AND cargo_vehicle_surcharge_kopecks >= 0
                AND cargo_loaders_surcharge_kopecks >= 0
                AND price_kopecks =
                    fare_base_price_kopecks
                    + fare_distance_price_kopecks
                    + fare_time_price_kopecks
                    + fare_limit_adjustment_kopecks
                    + anonymous_surcharge_kopecks
                    + child_seat_surcharge_kopecks
                    + animal_transport_surcharge_kopecks
                    + cargo_vehicle_surcharge_kopecks
                    + cargo_loaders_surcharge_kopecks
            )
            """,
            name="orders_fare_breakdown_consistent",
        ),
        Index(
            "ix_orders_city_status_created",
            "city_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    public_number: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id"),
        nullable=False,
        index=True,
    )

    tariff_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tariffs.id"),
        nullable=True,
        index=True,
    )

    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("branches.id"),
        nullable=True,
        index=True,
    )

    passenger_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("passenger_profiles.user_id"),
    )

    driver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("driver_profiles.user_id"),
        index=True,
    )

    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicles.id"),
    )

    customer_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    customer_phone: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    anonymous: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    pickup_address: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    destination_address: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    pickup_latitude: Mapped[float | None] = mapped_column(Float)
    pickup_longitude: Mapped[float | None] = mapped_column(Float)
    destination_latitude: Mapped[float | None] = mapped_column(Float)
    destination_longitude: Mapped[float | None] = mapped_column(Float)

    route_distance_meters: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    route_duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    routing_provider: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(40),
        default="new",
        nullable=False,
        index=True,
    )

    payment_method: Mapped[str] = mapped_column(
        String(30),
        default="cash",
        nullable=False,
    )

    price_rub: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    price_kopecks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    fare_base_price_kopecks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    fare_distance_price_kopecks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    fare_time_price_kopecks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    fare_limit_adjustment_kopecks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    anonymous_surcharge_kopecks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    child_seat: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    animal_transport: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    cargo_vehicle: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    cargo_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    cargo_loaders: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    child_seat_surcharge_kopecks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    animal_transport_surcharge_kopecks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    cargo_vehicle_surcharge_kopecks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    cargo_loaders_surcharge_kopecks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
    )


# ============================================================
# ORDER STATUS HISTORY
# ============================================================

class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id"),
        nullable=False,
        index=True,
    )

    old_status: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    new_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )


# ============================================================
# TARIFF CHANGE HISTORY
# Неизменяемый журнал изменений тарифов
# ============================================================

class TariffChangeHistory(Base):
    __tablename__ = "tariff_change_history"

    __table_args__ = (
        Index(
            "ix_tariff_history_city_changed",
            "city_id",
            "changed_at",
        ),
        Index(
            "ix_tariff_history_tariff_changed",
            "tariff_id",
            "changed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    tariff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tariffs.id", ondelete="RESTRICT"),
        nullable=False,
    )

    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id", ondelete="RESTRICT"),
        nullable=False,
    )

    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    old_values: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    new_values: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
        index=True,
    )
    

# ============================================================
# DRIVER FINANCE TRANSACTIONS
# Неизменяемый журнал финансовых операций водителей
# ============================================================

class DriverFinanceTransaction(Base):
    __tablename__ = "driver_finance_transactions"

    __table_args__ = (
        UniqueConstraint(
            "order_id",
            "transaction_type",
            name="uq_driver_finance_order_type",
        ),
        CheckConstraint(
            "fare_kopecks >= 0",
            name="driver_finance_fare_nonnegative",
        ),
        CheckConstraint(
            "commission_rate_percent >= 0 "
            "AND commission_rate_percent <= 100",
            name="driver_finance_commission_rate_range",
        ),
        CheckConstraint(
            "commission_kopecks >= 0",
            name="driver_finance_commission_nonnegative",
        ),
        CheckConstraint(
            "driver_earning_kopecks >= 0",
            name="driver_finance_earning_nonnegative",
        ),
        Index(
            "ix_driver_finance_driver_created",
            "driver_user_id",
            "created_at",
        ),
        Index(
            "ix_driver_finance_city_created",
            "city_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    driver_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "driver_profiles.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "orders.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "cities.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "branches.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    payment_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    driver_rating: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )

    fare_kopecks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    commission_rate_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )

    commission_kopecks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    driver_earning_kopecks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    debt_change_kopecks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )
