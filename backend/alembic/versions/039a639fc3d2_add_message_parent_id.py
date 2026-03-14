"""add message parent_id

Revision ID: 039a639fc3d2
Revises: 017
Create Date: 2026-03-13 23:26:32.386258

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "039a639fc3d2"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add parent_id column to messages table
    op.add_column("messages", sa.Column("parent_id", sa.UUID(), nullable=True))

    # 2. Create index for parent_id
    op.create_index(
        op.f("ix_messages_parent_id"), "messages", ["parent_id"], unique=False
    )

    # 3. Create self-referencing foreign key
    op.create_foreign_key(
        "fk_messages_parent_id",
        "messages",
        "messages",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",  # noqa: E501
    )


def downgrade() -> None:
    op.drop_constraint("fk_messages_parent_id", "messages", type_="foreignkey")
    op.drop_index(op.f("ix_messages_parent_id"), table_name="messages")
    op.drop_column("messages", "parent_id")
