
"""Add dispatcher and partner application tables.

Revision ID: 0003_applications
Revises: 0002_organizations
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_applications"
down_revision = "0002_organizations"
branch_labels = None
depends_on = None


APPLICATION_STATUS_CHECK = (
    "status IN ('new', 'reviewing', 'needs_info', 'approved', 'rejected')"
)


def upgrade() -> None:
    op.create_table(
        "dispatcher_applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("applicant_user_id", sa.Uuid(), nullable=True),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("requested_cities", sa.JSON(), nullable=False),
        sa.Column("experience", sa.Text(), nullable=True),
        sa.Column("applicant_message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("approved_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            APPLICATION_STATUS_CHECK,
            name="dispatcher_applications_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["applicant_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["approved_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_dispatcher_applications_applicant_user_id",
        "dispatcher_applications",
        ["applicant_user_id"],
    )
    op.create_index(
        "ix_dispatcher_applications_status",
        "dispatcher_applications",
        ["status"],
    )
    op.create_index(
        "ix_dispatcher_applications_status_created",
        "dispatcher_applications",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_dispatcher_applications_phone_status",
        "dispatcher_applications",
        ["phone", "status"],
    )

    op.create_table(
        "partner_applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("applicant_user_id", sa.Uuid(), nullable=True),
        sa.Column("contact_full_name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("organization_name", sa.String(length=200), nullable=False),
        sa.Column("legal_name", sa.String(length=250), nullable=True),
        sa.Column("tax_identifier", sa.String(length=20), nullable=True),
        sa.Column("requested_cities", sa.JSON(), nullable=False),
        sa.Column("fleet_size", sa.Integer(), nullable=True),
        sa.Column("applicant_message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            APPLICATION_STATUS_CHECK,
            name="partner_applications_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["applicant_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_partner_applications_applicant_user_id",
        "partner_applications",
        ["applicant_user_id"],
    )
    op.create_index(
        "ix_partner_applications_status",
        "partner_applications",
        ["status"],
    )
    op.create_index(
        "ix_partner_applications_organization_id",
        "partner_applications",
        ["organization_id"],
    )
    op.create_index(
        "ix_partner_applications_status_created",
        "partner_applications",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_partner_applications_phone_status",
        "partner_applications",
        ["phone", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_partner_applications_phone_status",
        table_name="partner_applications",
    )
    op.drop_index(
        "ix_partner_applications_status_created",
        table_name="partner_applications",
    )
    op.drop_index(
        "ix_partner_applications_organization_id",
        table_name="partner_applications",
    )
    op.drop_index(
        "ix_partner_applications_status",
        table_name="partner_applications",
    )
    op.drop_index(
        "ix_partner_applications_applicant_user_id",
        table_name="partner_applications",
    )
    op.drop_table("partner_applications")

    op.drop_index(
        "ix_dispatcher_applications_phone_status",
        table_name="dispatcher_applications",
    )
    op.drop_index(
        "ix_dispatcher_applications_status_created",
        table_name="dispatcher_applications",
    )
    op.drop_index(
        "ix_dispatcher_applications_status",
        table_name="dispatcher_applications",
    )
    op.drop_index(
        "ix_dispatcher_applications_applicant_user_id",
        table_name="dispatcher_applications",
    )
    op.drop_table("dispatcher_applications")
