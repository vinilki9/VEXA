
"""Add route metadata to orders.

Revision ID: 0002_add_order_route_metadata
Revises: 0001_initial_schema
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_order_route_metadata"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "route_distance_meters",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "orders",
        sa.Column(
            "route_duration_seconds",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "orders",
        sa.Column(
            "routing_provider",
            sa.String(length=40),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "routing_provider")
    op.drop_column("orders", "route_duration_seconds")
    op.drop_column("orders", "route_distance_meters")
