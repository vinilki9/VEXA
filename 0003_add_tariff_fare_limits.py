
"""Add minimum and maximum fare limits to tariffs.

Revision ID: 0003_add_tariff_fare_limits
Revises: 0002_add_order_route_metadata
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_tariff_fare_limits"
down_revision = "0002_add_order_route_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tariffs",
        sa.Column(
            "minimum_fare_kopecks",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "tariffs",
        sa.Column(
            "maximum_fare_kopecks",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "tariffs_minimum_fare_nonnegative",
        "tariffs",
        "minimum_fare_kopecks IS NULL OR minimum_fare_kopecks >= 0",
    )
    op.create_check_constraint(
        "tariffs_maximum_fare_nonnegative",
        "tariffs",
        "maximum_fare_kopecks IS NULL OR maximum_fare_kopecks >= 0",
    )
    op.create_check_constraint(
        "tariffs_maximum_fare_gte_minimum",
        "tariffs",
        """
        minimum_fare_kopecks IS NULL
        OR maximum_fare_kopecks IS NULL
        OR maximum_fare_kopecks >= minimum_fare_kopecks
        """,
    )


def downgrade() -> None:
    op.drop_constraint(
        "tariffs_maximum_fare_gte_minimum",
        "tariffs",
        type_="check",
    )
    op.drop_constraint(
        "tariffs_maximum_fare_nonnegative",
        "tariffs",
        type_="check",
    )
    op.drop_constraint(
        "tariffs_minimum_fare_nonnegative",
        "tariffs",
        type_="check",
    )

    op.drop_column("tariffs", "maximum_fare_kopecks")
    op.drop_column("tariffs", "minimum_fare_kopecks")
