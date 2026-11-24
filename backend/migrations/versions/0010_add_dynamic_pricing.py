
"""Add dynamic pricing settings and change history.

Revision ID: 0010_add_dynamic_pricing
Revises: 0009_add_driver_finance_transactions
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010_add_dynamic_pricing"
down_revision = "0009_add_driver_finance_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dynamic_pricing_settings",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "city_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cities.id", ondelete="RESTRICT"),
            nullable=False,
        ),

        sa.Column(
            "branch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=True,
        ),

        sa.Column(
            "max_multiplier",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="2.50",
        ),

        sa.Column(
            "driver_radius_km",
            sa.Numeric(6, 2),
            nullable=False,
            server_default="4.00",
        ),

        sa.Column(
            "driver_distance_start_multiplier",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="1.50",
        ),

        sa.Column(
            "driver_distance_threshold_km",
            sa.Numeric(6, 2),
            nullable=False,
            server_default="20.00",
        ),

        sa.Column(
            "driver_distance_threshold_multiplier",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="2.00",
        ),

        sa.Column(
            "driver_distance_step_km",
            sa.Numeric(6, 2),
            nullable=False,
            server_default="3.00",
        ),

        sa.Column(
            "driver_distance_step_multiplier",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0.20",
        ),

        sa.Column(
            "weather_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),

        sa.Column(
            "weather_addition",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0.00",
        ),

        sa.Column(
            "traffic_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),

        sa.Column(
            "traffic_addition",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0.00",
        ),

        sa.Column(
            "demand_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),

        sa.Column(
            "demand_addition",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0.00",
        ),

        sa.Column(
            "other_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),

        sa.Column(
            "other_addition",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0.00",
        ),

        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.CheckConstraint(
            "max_multiplier >= 1.0",
            name="dynamic_pricing_max_multiplier_min",
        ),

        sa.CheckConstraint(
            "driver_radius_km >= 0",
            name="dynamic_pricing_driver_radius_nonnegative",
        ),

        sa.CheckConstraint(
            "driver_distance_start_multiplier >= 1.0",
            name="dynamic_pricing_driver_start_min",
        ),

        sa.CheckConstraint(
            "driver_distance_threshold_km > driver_radius_km",
            name="dynamic_pricing_driver_threshold_gt_radius",
        ),

        sa.CheckConstraint(
            "driver_distance_threshold_multiplier >= "
            "driver_distance_start_multiplier",
            name="dynamic_pricing_driver_threshold_multiplier_valid",
        ),

        sa.CheckConstraint(
            "driver_distance_step_km > 0",
            name="dynamic_pricing_driver_step_km_positive",
        ),

        sa.CheckConstraint(
            "driver_distance_step_multiplier >= 0",
            name="dynamic_pricing_driver_step_multiplier_nonnegative",
        ),

        sa.UniqueConstraint(
            "city_id",
            "branch_id",
            name="uq_dynamic_pricing_city_branch",
        ),
    )

    op.create_index(
        "ix_dynamic_pricing_settings_city_id",
        "dynamic_pricing_settings",
        ["city_id"],
    )

    op.create_index(
        "ix_dynamic_pricing_settings_branch_id",
        "dynamic_pricing_settings",
        ["branch_id"],
    )

    op.create_index(
        "ix_dynamic_pricing_city_branch",
        "dynamic_pricing_settings",
        ["city_id", "branch_id"],
    )

    op.create_table(
        "dynamic_pricing_change_history",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "settings_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "dynamic_pricing_settings.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "city_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cities.id", ondelete="RESTRICT"),
            nullable=False,
        ),

        sa.Column(
            "branch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=True,
        ),

        sa.Column(
            "changed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),

        sa.Column(
            "action",
            sa.String(length=20),
            nullable=False,
        ),

        sa.Column(
            "old_values",
            sa.JSON(),
            nullable=True,
        ),

        sa.Column(
            "new_values",
            sa.JSON(),
            nullable=False,
        ),

        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_dynamic_pricing_change_history_settings_id",
        "dynamic_pricing_change_history",
        ["settings_id"],
    )

    op.create_index(
        "ix_dynamic_pricing_change_history_changed_by_user_id",
        "dynamic_pricing_change_history",
        ["changed_by_user_id"],
    )

    op.create_index(
        "ix_dynamic_pricing_history_city_changed",
        "dynamic_pricing_change_history",
        ["city_id", "changed_at"],
    )

    op.create_index(
        "ix_dynamic_pricing_history_settings_changed",
        "dynamic_pricing_change_history",
        ["settings_id", "changed_at"],
    )

    op.create_index(
        "ix_dynamic_pricing_change_history_changed_at",
        "dynamic_pricing_change_history",
        ["changed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dynamic_pricing_change_history_changed_at",
        table_name="dynamic_pricing_change_history",
    )

    op.drop_index(
        "ix_dynamic_pricing_history_settings_changed",
        table_name="dynamic_pricing_change_history",
    )

    op.drop_index(
        "ix_dynamic_pricing_history_city_changed",
        table_name="dynamic_pricing_change_history",
    )

    op.drop_index(
        "ix_dynamic_pricing_change_history_changed_by_user_id",
        table_name="dynamic_pricing_change_history",
    )

    op.drop_index(
        "ix_dynamic_pricing_change_history_settings_id",
        table_name="dynamic_pricing_change_history",
    )

    op.drop_table("dynamic_pricing_change_history")

    op.drop_index(
        "ix_dynamic_pricing_city_branch",
        table_name="dynamic_pricing_settings",
    )

    op.drop_index(
        "ix_dynamic_pricing_settings_branch_id",
        table_name="dynamic_pricing_settings",
    )

    op.drop_index(
        "ix_dynamic_pricing_settings_city_id",
        table_name="dynamic_pricing_settings",
    )

    op.drop_table("dynamic_pricing_settings")
