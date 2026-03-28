"""add conversation_folders table and folder_id to conversations

Revision ID: de1c6bd31f84
Revises: 3e2598640e52
Create Date: 2026-03-28 20:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "de1c6bd31f84"
down_revision: str | None = "3e2598640e52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_folders_user_id",
        "conversation_folders",
        ["user_id"],
    )

    op.add_column(
        "conversations",
        sa.Column("folder_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_folder_id",
        "conversations",
        "conversation_folders",
        ["folder_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_conversations_folder_id",
        "conversations",
        ["folder_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_folder_id", table_name="conversations")
    op.drop_constraint(
        "fk_conversations_folder_id", "conversations", type_="foreignkey"
    )
    op.drop_column("conversations", "folder_id")
    op.drop_index("ix_conversation_folders_user_id", table_name="conversation_folders")
    op.drop_table("conversation_folders")
