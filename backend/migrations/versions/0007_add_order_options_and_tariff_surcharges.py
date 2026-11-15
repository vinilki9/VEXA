
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
    # --------------------------------------------------------
    # TARIFFS: configurable additional service prices
    # --------------------------------------------------------

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

    with op.batch_alter_table("tariffs") as batch_op:
        batch_op.create_check_constraint(
            "tariffs_child_seat_surcharge_nonnegative",
            "child_seat_surcharge_kopecks >= 0",
        )

        batch_op.create_check_constraint(
            "tariffs_animal_surcharge_nonnegative",
            "animal_transport_surcharge_kopecks >= 0",
        )

        batch_op.create_check_constraint(
            "tariffs_cargo_loader_price_nonnegative",
            "cargo_loader_price_per_person_kopecks >= 0",
        )

    # --------------------------------------------------------
    # ORDERS: selected additional services and cargo details
    # --------------------------------------------------------

    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint(
            "orders_fare_breakdown_consistent",
            type_="check",
        )

        batch_op.add_column(
            sa.Column(
                "child_seat",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

        batch_op.add_column(
            sa.Column(
                "animal_transport",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

        batch_op.add_column(
            sa.Column(
                "cargo_vehicle",
                sa.String(length=80),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "cargo_description",
                sa.Text(),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "cargo_loaders",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )

        # Immutable additional-service price snapshots.
        batch_op.add_column(
            sa.Column(
                "child_seat_surcharge_kopecks",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "animal_transport_surcharge_kopecks",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "cargo_vehicle_surcharge_kopecks",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "cargo_loaders_surcharge_kopecks",
                sa.Integer(),
                nullable=True,
            )
        )

    # Existing orders already have the original fare breakdown.
    # Set the newly introduced components to zero for those orders.
    # Orders without a fare breakdown remain entirely NULL.
    op.execute(
        sa.text(
            """
            UPDATE orders
            SET
                child_seat_surcharge_kopecks = 0,
                animal_transport_surcharge_kopecks = 0,
                cargo_vehicle_surcharge_kopecks = 0,
                cargo_loaders_surcharge_kopecks = 0
            WHERE fare_base_price_kopecks IS NOT NULL
            """
        )
    )

    with op.batch_alter_table("orders") as batch_op:
        batch_op.create_check_constraint(
            "orders_cargo_loaders_range",
            "cargo_loaders >= 0 AND cargo_loaders <= 4",
        )

        batch_op.create_check_constraint(
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
    # Restore the original fare breakdown constraint.
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint(
            "orders_fare_breakdown_consistent",
            type_="check",
        )

        batch_op.drop_constraint(
            "orders_cargo_loaders_range",
            type_="check",
        )

        batch_op.create_check_constraint(
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

        batch_op.drop_column("cargo_loaders_surcharge_kopecks")
        batch_op.drop_column("cargo_vehicle_surcharge_kopecks")
        batch_op.drop_column("animal_transport_surcharge_kopecks")
        batch_op.drop_column("child_seat_surcharge_kopecks")
        batch_op.drop_column("cargo_loaders")
        batch_op.drop_column("cargo_description")
        batch_op.drop_column("cargo_vehicle")
        batch_op.drop_column("animal_transport")
        batch_op.drop_column("child_seat")

    with op.batch_alter_table("tariffs") as batch_op:
        batch_op.drop_constraint(
            "tariffs_cargo_loader_price_nonnegative",
            type_="check",
        )

        batch_op.drop_constraint(
            "tariffs_animal_surcharge_nonnegative",
            type_="check",
        )

        batch_op.drop_constraint(
            "tariffs_child_seat_surcharge_nonnegative",
            type_="check",
        )

        batch_op.drop_column(
            "cargo_loader_price_per_person_kopecks"
        )

        batch_op.drop_column(
            "cargo_vehicle_surcharges"
        )

        batch_op.drop_column(
            "animal_transport_surcharge_kopecks"
        )

        batch_op.drop_column(
            "child_seat_surcharge_kopecks"
        )
