
"""Add order options and tariff surcharges.

Revision ID: 0007_add_order_options_and_tariff_surcharges
Revises: 0006_add_passenger_auth_sessions
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_add_order_options_and_tariff_surcharges"
down_revision = "0006_add_passenger_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Новые параметры тарифов.
    op.add_column(
        "tariffs",
        sa.Column(
            "child_seat_surcharge_kopecks",
            sa.Integer(),
            nullable=False,
            server_default="10000",
        ),
    )
    op.add_column(
        "tariffs",
        sa.Column(
            "animal_transport_surcharge_kopecks",
            sa.Integer(),
            nullable=False,
            server_default="10000",
        ),
    )
    op.add_column(
        "tariffs",
        sa.Column(
            "cargo_vehicle_surcharges",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "tariffs",
        sa.Column(
            "cargo_loader_price_per_person_kopecks",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    with op.batch_alter_table("tariffs") as batch:
        batch.create_check_constraint(
            "tariffs_child_seat_surcharge_nonnegative",
            "child_seat_surcharge_kopecks >= 0",
        )
        batch.create_check_constraint(
            "tariffs_animal_surcharge_nonnegative",
            "animal_transport_surcharge_kopecks >= 0",
        )
        batch.create_check_constraint(
            "tariffs_cargo_loader_price_nonnegative",
            "cargo_loader_price_per_person_kopecks >= 0",
        )

    # Дополнительные параметры заказа.
    op.add_column(
        "orders",
        sa.Column(
            "child_seat",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "animal_transport",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "cargo_vehicle",
            sa.String(length=80),
            nullable=True,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "cargo_description",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "cargo_loaders",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # Сохранённые суммы дополнительных услуг.
    op.add_column(
        "orders",
        sa.Column(
            "child_seat_surcharge_kopecks",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "animal_transport_surcharge_kopecks",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "cargo_vehicle_surcharge_kopecks",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "cargo_loaders_surcharge_kopecks",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Старые заказы с полной расшифровкой получают нулевые
    # значения новых компонентов. Старые заказы без расшифровки
    # сохраняют NULL во всех компонентах.
    op.execute(
        """
        UPDATE orders
        SET
            child_seat_surcharge_kopecks = 0,
            animal_transport_surcharge_kopecks = 0,
            cargo_vehicle_surcharge_kopecks = 0,
            cargo_loaders_surcharge_kopecks = 0
        WHERE
            fare_base_price_kopecks IS NOT NULL
            AND fare_distance_price_kopecks IS NOT NULL
            AND fare_time_price_kopecks IS NOT NULL
            AND fare_limit_adjustment_kopecks IS NOT NULL
            AND anonymous_surcharge_kopecks IS NOT NULL
        """
    )

    with op.batch_alter_table("orders") as batch:
        batch.create_check_constraint(
            "orders_cargo_loaders_range",
            "cargo_loaders >= 0 AND cargo_loaders <= 4",
        )

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


def downgrade() -> None:
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
            )
            OR
            (
                fare_base_price_kopecks IS NOT NULL
                AND fare_distance_price_kopecks IS NOT NULL
                AND fare_time_price_kopecks IS NOT NULL
                AND fare_limit_adjustment_kopecks IS NOT NULL
                AND anonymous_surcharge_kopecks IS NOT NULL
                AND price_kopecks IS NOT NULL
                AND fare_base_price_kopecks >= 0
                AND fare_distance_price_kopecks >= 0
                AND fare_time_price_kopecks >= 0
                AND anonymous_surcharge_kopecks >= 0
                AND price_kopecks =
                    fare_base_price_kopecks
                    + fare_distance_price_kopecks
                    + fare_time_price_kopecks
                    + fare_limit_adjustment_kopecks
                    + anonymous_surcharge_kopecks
            )
            """,
        )

        batch.drop_constraint(
            "orders_cargo_loaders_range",
            type_="check",
        )

    op.drop_column("orders", "cargo_loaders_surcharge_kopecks")
    op.drop_column("orders", "cargo_vehicle_surcharge_kopecks")
    op.drop_column("orders", "animal_transport_surcharge_kopecks")
    op.drop_column("orders", "child_seat_surcharge_kopecks")
    op.drop_column("orders", "cargo_loaders")
    op.drop_column("orders", "cargo_description")
    op.drop_column("orders", "cargo_vehicle")
    op.drop_column("orders", "animal_transport")
    op.drop_column("orders", "child_seat")

    with op.batch_alter_table("tariffs") as batch:
        batch.drop_constraint(
            "tariffs_cargo_loader_price_nonnegative",
            type_="check",
        )
        batch.drop_constraint(
            "tariffs_animal_surcharge_nonnegative",
            type_="check",
        )
        batch.drop_constraint(
            "tariffs_child_seat_surcharge_nonnegative",
            type_="check",
        )

    op.drop_column("tariffs", "cargo_loader_price_per_person_kopecks")
    op.drop_column("tariffs", "cargo_vehicle_surcharges")
    op.drop_column("tariffs", "animal_transport_surcharge_kopecks")
    op.drop_column("tariffs", "child_seat_surcharge_kopecks")
