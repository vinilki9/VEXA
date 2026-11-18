
"""Merge driver transfer and driver order offer migration heads.

Revision ID: 0013_merge_migration_heads
Revises:
    0010_add_driver_branch_transfers
    0012_add_driver_order_offers
"""

revision = "0013_merge_migration_heads"
down_revision = (
    "0010_add_driver_branch_transfers",
    "0012_add_driver_order_offers",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
