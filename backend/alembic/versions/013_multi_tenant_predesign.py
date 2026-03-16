"""Multi-tenant DB predesign: organizations/workspaces tables + nullable FK columns.

Revision ID: 013
Revises: 012
Create Date: 2026-03-13
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create organizations table
    op.create_table(
        "organizations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_organizations_owner_id", "organizations", ["owner_id"])

    # Create workspaces table
    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_workspaces_organization_id", "workspaces", ["organization_id"])

    # Add nullable columns to existing tables
    op.add_column(
        "users",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])

    for table in ("conversations", "documents", "cron_jobs", "webhooks"):
        op.add_column(
            table,
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_index(f"ix_{table}_workspace_id", table, ["workspace_id"])


def downgrade() -> None:
    for table in ("conversations", "documents", "cron_jobs", "webhooks"):
        op.drop_index(f"ix_{table}_workspace_id", table_name=table)
        op.drop_column(table, "workspace_id")

    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_column("users", "organization_id")

    op.drop_index("ix_workspaces_organization_id", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index("ix_organizations_owner_id", table_name="organizations")
    op.drop_table("organizations")
