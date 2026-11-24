"""Immutable document revision acceptance evidence.

Revision ID: 0020_legal_history
Revises: 0019_legal_acceptances
"""
from alembic import op
import sqlalchemy as sa
revision = "0020_legal_history"
down_revision = "0019_legal_acceptances"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("legal_acceptances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("document_id", sa.String(100), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_source", sa.String(40), nullable=False),
        sa.UniqueConstraint("user_id", "role", "document_id", "version", "sha256", name="uq_legal_acceptance_revision"))
    op.create_index("ix_legal_acceptance_user_role", "legal_acceptances", ["user_id", "role"])

def downgrade():
    op.drop_index("ix_legal_acceptance_user_role", table_name="legal_acceptances")
    op.drop_table("legal_acceptances")
