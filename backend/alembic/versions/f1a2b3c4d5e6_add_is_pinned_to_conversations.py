"""add_is_pinned_to_conversations

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-03-19 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_conversations_is_pinned", "conversations", ["is_pinned"])


def downgrade() -> None:
    op.drop_index("ix_conversations_is_pinned", table_name="conversations")
    op.drop_column("conversations", "is_pinned")
