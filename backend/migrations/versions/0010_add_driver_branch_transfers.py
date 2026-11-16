
"""Add driver branch transfer history.

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
            "city_id",
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
            nullable=True,
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
            OR to_branch_id IS NULL
            OR from_branch_id != to_branch_id
            """,
            name="driver_branch_transfers_different_branches",
        ),
    )

    op.create_index(
        "ix_driver_branch_transfers_driver_user_id",
        "driver_branch_transfers",
        ["driver_user_id"],
    )

    op.create_index(
        "ix_driver_branch_transfers_city_id",
        "driver_branch_transfers",
        ["city_id"],
    )

    op.create_index(
        "ix_driver_branch_transfers_from_branch_id",
        "driver_branch_transfers",
        ["from_branch_id"],
    )

    op.create_index(
        "ix_driver_branch_transfers_to_branch_id",
        "driver_branch_transfers",
        ["to_branch_id"],
    )

    op.create_index(
        "ix_driver_branch_transfers_transferred_by_user_id",
        "driver_branch_transfers",
        ["transferred_by_user_id"],
    )

    op.create_index(
        "ix_driver_branch_transfers_driver_created",
        "driver_branch_transfers",
        ["driver_user_id", "created_at"],
    )

    op.create_index(
        "ix_driver_branch_transfers_city_created",
        "driver_branch_transfers",
        ["city_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("driver_branch_transfers")
