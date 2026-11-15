
"""Add passenger SMS authentication sessions.

Revision ID: 0006_add_passenger_auth_sessions
Revises: 0005_add_order_fare_breakdown
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_add_passenger_auth_sessions"
down_revision = "0005_add_order_fare_breakdown"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "passenger_auth_sessions",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "phone",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "provider_session_id",
            sa.String(length=120),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "provider_status",
            sa.String(length=80),
            nullable=True,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_passenger_auth_sessions_phone",
        "passenger_auth_sessions",
        ["phone"],
    )

    op.create_index(
        "ix_passenger_auth_phone_created",
        "passenger_auth_sessions",
        ["phone", "created_at"],
    )

    op.create_index(
        "ix_passenger_auth_expires",
        "passenger_auth_sessions",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_passenger_auth_expires",
        table_name="passenger_auth_sessions",
    )

    op.drop_index(
        "ix_passenger_auth_phone_created",
        table_name="passenger_auth_sessions",
    )

    op.drop_index(
        "ix_passenger_auth_sessions_phone",
        table_name="passenger_auth_sessions",
    )

    op.drop_table("passenger_auth_sessions")
