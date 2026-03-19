"""add_conversation_tags

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-03-19 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_tags",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "tag", name="uq_conversation_tags"),
    )
    op.create_index(
        "ix_conversation_tags_conversation_id",
        "conversation_tags",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_tags_conversation_id", table_name="conversation_tags"
    )
    op.drop_table("conversation_tags")
