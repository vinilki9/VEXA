"""Add opt-in included distance/time and operational charging policy.

Revision ID: 0017_tariff_inclusions
Revises: 0016_dispatch_pending_offer_uniqueness
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_tariff_inclusions"
down_revision = "0016_dispatch_pending_offer_uniqueness"
branch_labels = None
depends_on = None


_COLUMNS = (
    ("included_km", sa.Numeric(9, 3)),
    ("included_minutes", sa.Numeric(9, 2)),
    ("free_wait_minutes", sa.Numeric(9, 2)),
    ("waiting_price_per_minute_kopecks", sa.Integer()),
    ("stop_price_kopecks", sa.Integer()),
)
_CONSTRAINTS = (
    ("tariffs_included_km_nonnegative", "included_km >= 0"),
    ("tariffs_included_minutes_nonnegative", "included_minutes >= 0"),
    ("tariffs_free_wait_nonnegative", "free_wait_minutes >= 0"),
    ("tariffs_wait_price_nonnegative", "waiting_price_per_minute_kopecks >= 0"),
    ("tariffs_stop_price_nonnegative", "stop_price_kopecks >= 0"),
)


def upgrade() -> None:
    for name, column_type in _COLUMNS:
        op.add_column("tariffs", sa.Column(name, column_type, nullable=False, server_default="0"))
    for name, expression in _CONSTRAINTS:
        op.create_check_constraint(name, "tariffs", expression)


def downgrade() -> None:
    for name, _ in reversed(_CONSTRAINTS):
        op.drop_constraint(name, "tariffs", type_="check")
    for name, _ in reversed(_COLUMNS):
        op.drop_column("tariffs", name)
