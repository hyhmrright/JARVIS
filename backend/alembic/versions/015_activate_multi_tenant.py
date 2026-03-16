"""Activate multi-tenant: add Workspace.is_deleted, updated_at; add FK constraints.

Revision ID: 015
Revises: 014
Create Date: 2026-03-13
"""

import sqlalchemy as sa

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_users_organization_id",
        "users",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    for table in ("conversations", "documents", "cron_jobs", "webhooks"):
        op.create_foreign_key(
            f"fk_{table}_workspace_id",
            table,
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table in ("conversations", "documents", "cron_jobs", "webhooks"):
        op.drop_constraint(f"fk_{table}_workspace_id", table, type_="foreignkey")
    op.drop_constraint("fk_users_organization_id", "users", type_="foreignkey")
    op.drop_column("workspaces", "updated_at")
    op.drop_column("workspaces", "is_deleted")
