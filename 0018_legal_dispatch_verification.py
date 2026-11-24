"""Add snapshots of externally verified eligibility; NOT an automatic registry integration.

Revision ID: 0018_legal_dispatch
Revises: 0017_tariff_inclusions
"""
from alembic import op
import sqlalchemy as sa
revision = "0018_legal_dispatch"
down_revision = "0017_tariff_inclusions"
branch_labels = None
depends_on = None

def upgrade():
    columns = [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("driver_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("verified_by", sa.String(120), nullable=False),
    ]
    for field in ("carrier_registry_confirmed", "carrier_permission_active", "vehicle_registry_confirmed",
        "vehicle_registered_to_carrier", "driver_qualified", "driver_shift_compliant", "waybill_compliant",
        "insurance_verified", "carrier_identity_ready_for_passenger", "child_seats_compliant"):
        columns.append(sa.Column(field, sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("legal_dispatch_verifications", *columns,
        sa.CheckConstraint("valid_until > checked_at", name="ck_legal_verification_validity"),
        sa.CheckConstraint("length(trim(source_reference)) > 0", name="ck_legal_verification_source"))
    op.create_index("ix_legal_verification_driver_vehicle", "legal_dispatch_verifications", ["driver_user_id", "vehicle_id"])

def downgrade():
    op.drop_index("ix_legal_verification_driver_vehicle", table_name="legal_dispatch_verifications")
    op.drop_table("legal_dispatch_verifications")
