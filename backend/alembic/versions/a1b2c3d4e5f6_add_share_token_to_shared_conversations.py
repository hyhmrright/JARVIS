"""add_share_token_to_shared_conversations

Revision ID: a1b2c3d4e5f6
Revises: 023f0ff81c26
Create Date: 2026-03-16 22:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "023f0ff81c26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add share_token column; backfill existing rows with a unique opaque token,
    # then enforce NOT NULL and unique constraints.
    op.add_column(
        "shared_conversations",
        sa.Column("share_token", sa.String(64), nullable=True),
    )
    # Backfill: produce a URL-safe base64 token matching secrets.token_urlsafe(32).
    # rtrim strips trailing '=' padding and the '\n' that PostgreSQL appends to
    # base64 output; the two replace() calls swap standard-base64 chars to URL-safe.
    op.execute(
        "UPDATE shared_conversations "
        "SET share_token = rtrim("
        "    replace("
        "        replace(encode(gen_random_bytes(32), 'base64'), '+', '-'),"
        "        '/', '_'"
        "    ),"
        "    E'=\\n'"
        ") "
        "WHERE share_token IS NULL"
    )
    op.alter_column("shared_conversations", "share_token", nullable=False)
    op.create_index(
        "ix_shared_conversations_share_token",
        "shared_conversations",
        ["share_token"],
        unique=True,
    )
    # Enforce one share per conversation at the DB level to prevent TOCTOU duplicates.
    op.create_unique_constraint(
        "uq_shared_conversations_conversation_id",
        "shared_conversations",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_shared_conversations_conversation_id",
        "shared_conversations",
        type_="unique",
    )
    op.drop_index(
        "ix_shared_conversations_share_token", table_name="shared_conversations"
    )
    op.drop_column("shared_conversations", "share_token")
