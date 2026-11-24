
"""Add driver order offers.

Revision ID: 0012_add_driver_order_offers
Revises: 0011_add_order_dynamic_pricing_snapshot
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0012_add_driver_order_offers"
down_revision = "0011_add_order_dynamic_pricing_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "driver_order_offers",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "orders.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "driver_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "driver_profiles.user_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "vehicle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "vehicles.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
        ),

        sa.Column(
            "attempt_number",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "response_timeout_seconds",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "distance_meters",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "offered_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "responded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.UniqueConstraint(
            "order_id",
            "driver_user_id",
            name="uq_driver_order_offers_order_driver",
        ),

        sa.CheckConstraint(
            "status IN "
            "('pending', 'accepted', 'rejected', 'expired', 'cancelled')",
            name="driver_order_offers_status_valid",
        ),

        sa.CheckConstraint(
            "response_timeout_seconds > 0",
            name="driver_order_offers_timeout_positive",
        ),

        sa.CheckConstraint(
            "distance_meters IS NULL OR distance_meters >= 0",
            name="driver_order_offers_distance_nonnegative",
        ),
    )

    op.create_index(
        "ix_driver_order_offers_order_status",
        "driver_order_offers",
        ["order_id", "status"],
    )

    op.create_index(
        "ix_driver_order_offers_driver_status",
        "driver_order_offers",
        ["driver_user_id", "status"],
    )

    op.create_index(
        "ix_driver_order_offers_status_expires",
        "driver_order_offers",
        ["status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_table("driver_order_offers")
