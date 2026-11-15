
"""Add last known driver locations.

Revision ID: 0008_add_driver_locations
Revises: 0007_add_order_options_and_tariff_surcharges
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_add_driver_locations"
down_revision = "0007_add_order_options_and_tariff_surcharges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "driver_locations",
        sa.Column(
            "driver_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "driver_profiles.user_id",
                ondelete="CASCADE",
            ),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "latitude",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "longitude",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "accuracy_meters",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="driver_locations_latitude_range",
        ),
        sa.CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="driver_locations_longitude_range",
        ),
        sa.CheckConstraint(
            "accuracy_meters IS NULL OR accuracy_meters >= 0",
            name="driver_locations_accuracy_nonnegative",
        ),
    )

    op.create_index(
        "ix_driver_locations_recorded_at",
        "driver_locations",
        ["recorded_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_driver_locations_recorded_at",
        table_name="driver_locations",
    )
    op.drop_table("driver_locations")
