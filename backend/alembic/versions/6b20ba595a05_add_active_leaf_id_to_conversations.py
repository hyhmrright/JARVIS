"""add active_leaf_id to conversations

Revision ID: 6b20ba595a05
Revises: fdcf42e184ee
Create Date: 2026-03-16 23:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b20ba595a05"
down_revision: str | None = "fdcf42e184ee"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "active_leaf_id",
            UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_conversations_active_leaf_id", "conversations", ["active_leaf_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "conversations_active_leaf_id_fkey", "conversations", type_="foreignkey"
    )
    op.drop_index("ix_conversations_active_leaf_id", table_name="conversations")
    op.drop_column("conversations", "active_leaf_id")
