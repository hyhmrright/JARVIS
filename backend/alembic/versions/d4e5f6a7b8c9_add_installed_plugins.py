"""add_installed_plugins

Revision ID: d4e5f6a7b8c9
Revises: c7c0b68bab0e
Create Date: 2026-03-18 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c7c0b68bab0e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "installed_plugins",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("plugin_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("install_url", sa.Text, nullable=False),
        sa.Column("mcp_command", sa.String(200), nullable=True),
        sa.Column("mcp_args", JSONB, nullable=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column(
            "installed_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN ('mcp', 'skill_md', 'python_plugin')",
            name="installed_plugins_type_check",
        ),
        sa.CheckConstraint(
            "scope IN ('system', 'personal')",
            name="installed_plugins_scope_check",
        ),
    )
    # Personal installs: unique per user per plugin
    op.create_index(
        "installed_plugins_personal_unique",
        "installed_plugins",
        ["plugin_id", "installed_by"],
        unique=True,
        postgresql_where=sa.text("scope = 'personal'"),
    )
    # System installs: unique globally (installed_by IS NULL)
    op.create_index(
        "installed_plugins_system_unique",
        "installed_plugins",
        ["plugin_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'system'"),
    )
    # Lookup index for per-request tool loading
    op.create_index(
        "installed_plugins_scope_user",
        "installed_plugins",
        ["scope", "installed_by"],
    )


def downgrade() -> None:
    op.drop_index("installed_plugins_scope_user", table_name="installed_plugins")
    op.drop_index("installed_plugins_system_unique", table_name="installed_plugins")
    op.drop_index("installed_plugins_personal_unique", table_name="installed_plugins")
    op.drop_table("installed_plugins")
