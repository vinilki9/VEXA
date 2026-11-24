
"""Add tariff change history.

Revision ID: 0004_add_tariff_change_history
Revises: 0003_add_tariff_fare_limits
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_tariff_change_history"
down_revision = "0003_add_tariff_fare_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tariff_change_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tariff_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("old_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tariff_id"],
            ["tariffs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["cities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_tariff_history_city_changed",
        "tariff_change_history",
        ["city_id", "changed_at"],
    )

    op.create_index(
        "ix_tariff_history_tariff_changed",
        "tariff_change_history",
        ["tariff_id", "changed_at"],
    )

    op.create_index(
        "ix_tariff_change_history_changed_by_user_id",
        "tariff_change_history",
        ["changed_by_user_id"],
    )

    op.create_index(
        "ix_tariff_change_history_changed_at",
        "tariff_change_history",
        ["changed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tariff_change_history_changed_at",
        table_name="tariff_change_history",
    )
    op.drop_index(
        "ix_tariff_change_history_changed_by_user_id",
        table_name="tariff_change_history",
    )
    op.drop_index(
        "ix_tariff_history_tariff_changed",
        table_name="tariff_change_history",
    )
    op.drop_index(
        "ix_tariff_history_city_changed",
        table_name="tariff_change_history",
    )
    op.drop_table("tariff_change_history")
