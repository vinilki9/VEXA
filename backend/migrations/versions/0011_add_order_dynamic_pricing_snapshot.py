
"""Add dynamic pricing snapshot to orders.

Revision ID: 0011_add_order_dynamic_pricing_snapshot
Revises: 0010_add_dynamic_pricing
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0011_add_order_dynamic_pricing_snapshot"
down_revision = "0010_add_dynamic_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "dynamic_pricing_settings_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.add_column(
        "orders",
        sa.Column(
            "dynamic_pricing_multiplier",
            sa.Numeric(5, 2),
            nullable=True,
        ),
    )

    op.add_column(
        "orders",
        sa.Column(
            "dynamic_driver_distance_km",
            sa.Numeric(8, 2),
            nullable=True,
        ),
    )

    op.add_column(
        "orders",
        sa.Column(
            "fare_dynamic_adjustment_kopecks",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "orders",
        sa.Column(
            "dynamic_pricing_breakdown",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_orders_dynamic_pricing_settings_id_dynamic_pricing_settings",
        "orders",
        "dynamic_pricing_settings",
        ["dynamic_pricing_settings_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        "ix_orders_dynamic_pricing_settings_id",
        "orders",
        ["dynamic_pricing_settings_id"],
    )

    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint(
            "orders_fare_breakdown_consistent",
            type_="check",
        )

        batch.create_check_constraint(
            "orders_fare_breakdown_consistent",
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
                AND fare_dynamic_adjustment_kopecks IS NULL
            )
            OR
            (
                fare_base_price_kopecks IS NOT NULL
                AND fare_dynamic_adjustment_kopecks IS NOT NULL
                AND fare_distance_price_kopecks IS NOT NULL
                AND fare_time_price_kopecks IS NOT NULL
                AND fare_limit_adjustment_kopecks IS NOT NULL
                AND anonymous_surcharge_kopecks IS NOT NULL
                AND child_seat_surcharge_kopecks IS NOT NULL
                AND animal_transport_surcharge_kopecks IS NOT NULL
                AND cargo_vehicle_surcharge_kopecks IS NOT NULL
                AND cargo_loaders_surcharge_kopecks IS NOT NULL
                AND price_kopecks IS NOT NULL
                AND fare_dynamic_adjustment_kopecks >= 0
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
                    + fare_dynamic_adjustment_kopecks
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
        )


def downgrade() -> None:
    # Не допускаем откат, если в заказах уже есть
    # положительная динамическая надбавка: старое ограничение
    # стоимости не сможет проверить такие заказы корректно.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM orders
                WHERE fare_dynamic_adjustment_kopecks > 0
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: orders contain dynamic fare adjustments';
            END IF;
        END
        $$;
        """
    )

    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint(
            "orders_fare_breakdown_consistent",
            type_="check",
        )

        batch.create_check_constraint(
            "orders_fare_breakdown_consistent",
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
        )

    op.drop_index(
        "ix_orders_dynamic_pricing_settings_id",
        table_name="orders",
    )

    op.drop_constraint(
        "fk_orders_dynamic_pricing_settings_id_dynamic_pricing_settings",
        "orders",
        type_="foreignkey",
    )

    op.drop_column("orders", "dynamic_pricing_breakdown")
    op.drop_column("orders", "fare_dynamic_adjustment_kopecks")
    op.drop_column("orders", "dynamic_driver_distance_km")
    op.drop_column("orders", "dynamic_pricing_multiplier")
    op.drop_column("orders", "dynamic_pricing_settings_id")
