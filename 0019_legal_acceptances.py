"""Store versioned legal selections per SMS authorization session.

Revision ID: 0019_legal_acceptances
Revises: 0018_legal_dispatch
"""
from alembic import op
import sqlalchemy as sa
revision = "0019_legal_acceptances"
down_revision = "0018_legal_dispatch"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("passenger_auth_sessions", sa.Column("legal_acceptances", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))

def downgrade():
    op.drop_column("passenger_auth_sessions", "legal_acceptances")
