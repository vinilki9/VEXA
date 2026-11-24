
"""Add organization management tables.

Revision ID: 0002_organizations
Revises: 0001_initial_schema
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_organizations"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'suspended', 'rejected')",
            name="organizations_status_valid",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(
        "ix_organizations_slug",
        "organizations",
        ["slug"],
        unique=False,
    )
    op.create_index(
        "ix_organizations_status",
        "organizations",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_organizations_status_created",
        "organizations",
        ["status", "created_at"],
        unique=False,
    )

    op.create_table(
        "organization_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            name="uq_organization_settings_organization",
        ),
    )
    op.create_index(
        "ix_organization_settings_organization_id",
        "organization_settings",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "organization_cities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["cities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "city_id",
            name="uq_organization_cities_organization_city",
        ),
    )
    op.create_index(
        "ix_organization_cities_organization_id",
        "organization_cities",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_cities_city_id",
        "organization_cities",
        ["city_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_cities_city_active",
        "organization_cities",
        ["city_id", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_cities_city_active",
        table_name="organization_cities",
    )
    op.drop_index(
        "ix_organization_cities_city_id",
        table_name="organization_cities",
    )
    op.drop_index(
        "ix_organization_cities_organization_id",
        table_name="organization_cities",
    )
    op.drop_table("organization_cities")

    op.drop_index(
        "ix_organization_settings_organization_id",
        table_name="organization_settings",
    )
    op.drop_table("organization_settings")

    op.drop_index(
        "ix_organizations_status_created",
        table_name="organizations",
    )
    op.drop_index(
        "ix_organizations_status",
        table_name="organizations",
    )
    op.drop_index(
        "ix_organizations_slug",
        table_name="organizations",
    )
    op.drop_table("organizations")
