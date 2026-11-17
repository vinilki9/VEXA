
"""Add driver branch and city transfer history.

Revision ID: 0010_add_driver_branch_transfers
Revises: 0009_add_driver_finance_transactions
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010_add_driver_branch_transfers"
down_revision = "0009_add_driver_finance_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "driver_branch_transfers",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
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
            "from_city_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "cities.id",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),

        sa.Column(
            "to_city_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "cities.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "from_branch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "branches.id",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),

        sa.Column(
            "to_branch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "branches.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "debt_kopecks_at_transfer",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "transferred_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.CheckConstraint(
            "debt_kopecks_at_transfer >= 0",
            name="driver_branch_transfers_debt_nonnegative",
        ),

        sa.CheckConstraint(
            """
            from_branch_id IS NULL
            OR from_branch_id != to_branch_id
            """,
            name="driver_branch_transfers_different_branches",
        ),
    )

    indexes = (
        ("driver_user_id",),
        ("from_city_id",),
        ("to_city_id",),
        ("from_branch_id",),
        ("to_branch_id",),
        ("transferred_by_user_id",),
        ("driver_user_id", "created_at"),
        ("from_city_id", "created_at"),
        ("to_city_id", "created_at"),
    )

    for columns in indexes:
        index_name = (
            "ix_driver_branch_transfers_"
            + "_".join(columns)
        )

        op.create_index(
            index_name,
            "driver_branch_transfers",
            list(columns),
        )


def downgrade() -> None:
    op.drop_table("driver_branch_transfers")
