"""add_user_memories

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-03-19 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_memories",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column(
            "category",
            sa.String(50),
            nullable=False,
            server_default="general",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "key", name="uq_user_memories_user_key"),
        sa.CheckConstraint(
            "category IN ('preference', 'fact', 'reminder', 'general')",
            name="ck_user_memories_category",
        ),
    )
    op.create_index("ix_user_memories_user_id", "user_memories", ["user_id"])
    op.create_index("ix_user_memories_category", "user_memories", ["category"])


def downgrade() -> None:
    op.drop_index("ix_user_memories_category", table_name="user_memories")
    op.drop_index("ix_user_memories_user_id", table_name="user_memories")
    op.drop_table("user_memories")
