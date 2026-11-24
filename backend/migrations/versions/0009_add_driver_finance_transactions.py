
"""Add driver finance transaction ledger.

Revision ID: 0009_add_driver_finance_transactions
Revises: 0008_add_driver_locations
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_add_driver_finance_transactions"
down_revision = "0008_add_driver_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "driver_finance_transactions",

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
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "orders.id",
                ondelete="RESTRICT",
            ),
            nullable=True,
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
            "branch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "branches.id",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),

        sa.Column(
            "transaction_type",
            sa.String(length=40),
            nullable=False,
        ),

        sa.Column(
            "payment_method",
            sa.String(length=30),
            nullable=False,
        ),

        sa.Column(
            "driver_rating",
            sa.Numeric(3, 2),
            nullable=True,
        ),

        sa.Column(
            "fare_kopecks",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "commission_rate_percent",
            sa.Numeric(5, 2),
            nullable=False,
        ),

        sa.Column(
            "commission_kopecks",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "driver_earning_kopecks",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "debt_change_kopecks",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.UniqueConstraint(
            "order_id",
            "transaction_type",
            name="uq_driver_finance_order_type",
        ),

        sa.CheckConstraint(
            "fare_kopecks >= 0",
            name="driver_finance_fare_nonnegative",
        ),

        sa.CheckConstraint(
            "commission_rate_percent >= 0 "
            "AND commission_rate_percent <= 100",
            name="driver_finance_commission_rate_range",
        ),

        sa.CheckConstraint(
            "commission_kopecks >= 0",
            name="driver_finance_commission_nonnegative",
        ),

        sa.CheckConstraint(
            "driver_earning_kopecks >= 0",
            name="driver_finance_earning_nonnegative",
        ),
    )

    op.create_index(
        "ix_driver_finance_transactions_driver_user_id",
        "driver_finance_transactions",
        ["driver_user_id"],
    )

    op.create_index(
        "ix_driver_finance_transactions_order_id",
        "driver_finance_transactions",
        ["order_id"],
    )

    op.create_index(
        "ix_driver_finance_transactions_city_id",
        "driver_finance_transactions",
        ["city_id"],
    )

    op.create_index(
        "ix_driver_finance_transactions_branch_id",
        "driver_finance_transactions",
        ["branch_id"],
    )

    op.create_index(
        "ix_driver_finance_driver_created",
        "driver_finance_transactions",
        ["driver_user_id", "created_at"],
    )

    op.create_index(
        "ix_driver_finance_city_created",
        "driver_finance_transactions",
        ["city_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_driver_finance_city_created",
        table_name="driver_finance_transactions",
    )

    op.drop_index(
        "ix_driver_finance_driver_created",
        table_name="driver_finance_transactions",
    )

    op.drop_index(
        "ix_driver_finance_transactions_branch_id",
        table_name="driver_finance_transactions",
    )

    op.drop_index(
        "ix_driver_finance_transactions_city_id",
        table_name="driver_finance_transactions",
    )

    op.drop_index(
        "ix_driver_finance_transactions_order_id",
        table_name="driver_finance_transactions",
    )

    op.drop_index(
        "ix_driver_finance_transactions_driver_user_id",
        table_name="driver_finance_transactions",
    )

    op.drop_table("driver_finance_transactions")
