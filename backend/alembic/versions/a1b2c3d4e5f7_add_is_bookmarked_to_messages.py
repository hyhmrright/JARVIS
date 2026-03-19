"""add_is_bookmarked_to_messages

Revision ID: a1b2c3d4e5f7
Revises: fdcf42e184ee
Create Date: 2026-03-19 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: str | None = "fdcf42e184ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "is_bookmarked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_messages_is_bookmarked",
        "messages",
        ["is_bookmarked"],
        postgresql_where=sa.text("is_bookmarked = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_messages_is_bookmarked", table_name="messages")
    op.drop_column("messages", "is_bookmarked")
