
"""Add immutable fare breakdown snapshot to orders.

Revision ID: 0005_add_order_fare_breakdown
Revises: 0004_add_tariff_change_history
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_add_order_fare_breakdown"
down_revision = "0004_add_tariff_change_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("fare_base_price_kopecks", sa.Integer(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("fare_distance_price_kopecks", sa.Integer(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("fare_time_price_kopecks", sa.Integer(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("fare_limit_adjustment_kopecks", sa.Integer(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("anonymous_surcharge_kopecks", sa.Integer(), nullable=True),
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


def downgrade() -> None:
    op.drop_constraint(
        "orders_fare_breakdown_consistent",
        "orders",
        type_="check",
    )

    op.drop_column("orders", "anonymous_surcharge_kopecks")
    op.drop_column("orders", "fare_limit_adjustment_kopecks")
    op.drop_column("orders", "fare_time_price_kopecks")
    op.drop_column("orders", "fare_distance_price_kopecks")
    op.drop_column("orders", "fare_base_price_kopecks")
