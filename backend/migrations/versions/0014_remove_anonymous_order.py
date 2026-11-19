
"""Remove anonymous orders and make passenger name mandatory.

Revision ID: 0014_remove_anonymous_order
Revises: 0013_merge_migration_heads
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_remove_anonymous_order"
down_revision = "0013_merge_migration_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Сохраняем старые заказы без имени, не придумывая личные данные.
    op.execute(
        """
        UPDATE orders
        SET customer_name = 'Не указано'
        WHERE customer_name IS NULL
           OR BTRIM(customer_name) = ''
        """
    )

    # Убираем старое ограничение, в котором учитывалась
    # доплата за анонимный заказ.
    op.drop_constraint(
        "orders_fare_breakdown_consistent",
        "orders",
        type_="check",
    )

    op.drop_column("orders", "anonymous_surcharge_kopecks")
    op.drop_column("orders", "anonymous")

    op.alter_column(
        "orders",
        "customer_name",
        existing_type=sa.String(length=120),
        nullable=False,
    )

    # Новая проверка суммы без компонента анонимной доплаты.
    op.create_check_constraint(
        "orders_fare_breakdown_consistent",
        "orders",
        """
        (
            fare_base_price_kopecks IS NULL
            AND fare_distance_price_kopecks IS NULL
            AND fare_time_price_kopecks IS NULL
            AND fare_limit_adjustment_kopecks IS NULL
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
            AND child_seat_surcharge_kopecks IS NOT NULL
            AND animal_transport_surcharge_kopecks IS NOT NULL
            AND cargo_vehicle_surcharge_kopecks IS NOT NULL
            AND cargo_loaders_surcharge_kopecks IS NOT NULL
            AND price_kopecks IS NOT NULL
            AND fare_dynamic_adjustment_kopecks >= 0
            AND fare_base_price_kopecks >= 0
            AND fare_distance_price_kopecks >= 0
            AND fare_time_price_kopecks >= 0
            AND fare_limit_adjustment_kopecks >= 0
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
                + child_seat_surcharge_kopecks
                + animal_transport_surcharge_kopecks
                + cargo_vehicle_surcharge_kopecks
                + cargo_loaders_surcharge_kopecks
        )
        """,
    )


def downgrade() -> None:
    # При откате возвращаем старую структуру столбцов.
    # Исторические значения анонимности восстановить невозможно:
    # они удалены при upgrade.
    op.add_column(
        "orders",
        sa.Column(
            "anonymous",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.alter_column(
        "orders",
        "anonymous",
        existing_type=sa.Boolean(),
        server_default=None,
    )

    op.add_column(
        "orders",
        sa.Column(
            "anonymous_surcharge_kopecks",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Для старых заказов с полной расшифровкой устанавливаем
    # нулевую анонимную доплату.
    op.execute(
        """
        UPDATE orders
        SET anonymous_surcharge_kopecks = 0
        WHERE fare_base_price_kopecks IS NOT NULL
          AND fare_dynamic_adjustment_kopecks IS NOT NULL
          AND fare_distance_price_kopecks IS NOT NULL
          AND fare_time_price_kopecks IS NOT NULL
          AND fare_limit_adjustment_kopecks IS NOT NULL
          AND child_seat_surcharge_kopecks IS NOT NULL
          AND animal_transport_surcharge_kopecks IS NOT NULL
          AND cargo_vehicle_surcharge_kopecks IS NOT NULL
          AND cargo_loaders_surcharge_kopecks IS NOT NULL
        """
    )

    op.alter_column(
        "orders",
        "customer_name",
        existing_type=sa.String(length=120),
        nullable=True,
    )

    op.drop_constraint(
        "orders_fare_breakdown_consistent",
        "orders",
        type_="check",
    )

    op.create_check_constraint(
        "orders_fare_breakdown_consistent",
        "orders",
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
