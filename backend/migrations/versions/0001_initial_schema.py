
"""Initial VEXA database schema.

Revision ID: 0001_initial_schema
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cities",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_cities_code", "cities", ["code"])

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("username", sa.String(80), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("phone"),
    )

    op.create_table(
        "branches",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("city_id", sa.Uuid(), sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("city_id", "name", name="uq_branches_city_name"),
    )
    op.create_index("ix_branches_city_id", "branches", ["city_id"])

    op.create_table(
        "tariffs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("city_id", sa.Uuid(), sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("vehicle_class", sa.String(80), nullable=False),
        sa.Column("base_price_kopecks", sa.Integer(), nullable=False),
        sa.Column("price_per_km_kopecks", sa.Integer(), nullable=False),
        sa.Column("price_per_minute_kopecks", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("city_id", "code", name="uq_tariffs_city_code"),
        sa.CheckConstraint("base_price_kopecks >= 0", name="tariffs_base_price_nonnegative"),
        sa.CheckConstraint("price_per_km_kopecks >= 0", name="tariffs_price_per_km_nonnegative"),
        sa.CheckConstraint("price_per_minute_kopecks >= 0", name="tariffs_price_per_minute_nonnegative"),
    )
    op.create_index("ix_tariffs_city_id", "tariffs", ["city_id"])

    op.create_table(
        "passenger_profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("display_name", sa.String(120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "driver_profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("city_id", sa.Uuid(), sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_online", sa.Boolean(), nullable=False),
        sa.Column("rating", sa.Numeric(3, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_driver_profiles_city_id", "driver_profiles", ["city_id"])
    op.create_index("ix_driver_profiles_branch_id", "driver_profiles", ["branch_id"])

    op.create_table(
        "dispatcher_profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dispatcher_profiles_branch_id", "dispatcher_profiles", ["branch_id"])

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("driver_user_id", sa.Uuid(), sa.ForeignKey("driver_profiles.user_id"), nullable=False),
        sa.Column("city_id", sa.Uuid(), sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("make", sa.String(80), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("color", sa.String(50), nullable=False),
        sa.Column("license_plate", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("license_plate"),
    )
    op.create_index("ix_vehicles_driver_user_id", "vehicles", ["driver_user_id"])
    op.create_index("ix_vehicles_city_id", "vehicles", ["city_id"])

    op.create_table(
        "city_order_counters",
        sa.Column("city_id", sa.Uuid(), sa.ForeignKey("cities.id"), primary_key=True),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("public_number", sa.String(40), nullable=False),
        sa.Column("city_id", sa.Uuid(), sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("tariff_id", sa.Uuid(), sa.ForeignKey("tariffs.id"), nullable=True),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("passenger_user_id", sa.Uuid(), sa.ForeignKey("passenger_profiles.user_id"), nullable=True),
        sa.Column("driver_user_id", sa.Uuid(), sa.ForeignKey("driver_profiles.user_id"), nullable=True),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("customer_name", sa.String(120), nullable=True),
        sa.Column("customer_phone", sa.String(40), nullable=False),
        sa.Column("anonymous", sa.Boolean(), nullable=False),
        sa.Column("pickup_address", sa.String(500), nullable=False),
        sa.Column("destination_address", sa.String(500), nullable=False),
        sa.Column("pickup_latitude", sa.Float(), nullable=True),
        sa.Column("pickup_longitude", sa.Float(), nullable=True),
        sa.Column("destination_latitude", sa.Float(), nullable=True),
        sa.Column("destination_longitude", sa.Float(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("price_rub", sa.Integer(), nullable=True),
        sa.Column("price_kopecks", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("city_id", "idempotency_key", name="uq_orders_city_idempotency"),
        sa.UniqueConstraint("public_number", name="uq_orders_public_number"),
        sa.CheckConstraint("price_rub IS NULL OR price_rub >= 0", name="orders_price_rub_nonnegative"),
        sa.CheckConstraint("price_kopecks IS NULL OR price_kopecks >= 0", name="orders_price_kopecks_nonnegative"),
    )
    op.create_index("ix_orders_city_id", "orders", ["city_id"])
    op.create_index("ix_orders_tariff_id", "orders", ["tariff_id"])
    op.create_index("ix_orders_branch_id", "orders", ["branch_id"])
    op.create_index("ix_orders_driver_user_id", "orders", ["driver_user_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_city_status_created", "orders", ["city_id", "status", "created_at"])

    op.create_table(
        "order_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("old_status", sa.String(40), nullable=True),
        sa.Column("new_status", sa.String(40), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_order_status_history_order_id", "order_status_history", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_status_history_order_id", table_name="order_status_history")
    op.drop_table("order_status_history")

    op.drop_index("ix_orders_city_status_created", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_driver_user_id", table_name="orders")
    op.drop_index("ix_orders_branch_id", table_name="orders")
    op.drop_index("ix_orders_tariff_id", table_name="orders")
    op.drop_index("ix_orders_city_id", table_name="orders")
    op.drop_table("orders")

    op.drop_table("city_order_counters")

    op.drop_index("ix_vehicles_city_id", table_name="vehicles")
    op.drop_index("ix_vehicles_driver_user_id", table_name="vehicles")
    op.drop_table("vehicles")

    op.drop_index("ix_dispatcher_profiles_branch_id", table_name="dispatcher_profiles")
    op.drop_table("dispatcher_profiles")

    op.drop_index("ix_driver_profiles_branch_id", table_name="driver_profiles")
    op.drop_index("ix_driver_profiles_city_id", table_name="driver_profiles")
    op.drop_table("driver_profiles")

    op.drop_table("passenger_profiles")

    op.drop_index("ix_tariffs_city_id", table_name="tariffs")
    op.drop_table("tariffs")

    op.drop_index("ix_branches_city_id", table_name="branches")
    op.drop_table("branches")

    op.drop_table("users")

    op.drop_index("ix_cities_code", table_name="cities")
    op.drop_table("cities")
