"""Ensure each driver has at most one pending order offer.

Revision ID: 0016_dispatch_pending_offer_uniqueness
Revises: 0015_organization_access

Before applying on an existing database, check and resolve any duplicate
pending offers per driver (see release report). Migration fails safely if
duplicates remain; it never silently changes active offers.
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_dispatch_pending_offer_uniqueness"
down_revision = "0015_organization_access"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_driver_order_offers_one_pending_per_driver", "driver_order_offers",
        ["driver_user_id"], unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade():
    op.drop_index("uq_driver_order_offers_one_pending_per_driver", table_name="driver_order_offers")
