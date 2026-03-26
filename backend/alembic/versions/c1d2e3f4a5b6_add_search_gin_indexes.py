"""Add pg_trgm extension and GIN indexes for full-text search

Revision ID: c1d2e3f4a5b6
Revises: fdcf42e184ee
Create Date: 2026-03-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "fdcf42e184ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_messages_content_trgm "
            "ON messages USING gin (content gin_trgm_ops)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_memories_value_trgm "
            "ON user_memories USING gin (value gin_trgm_ops)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_documents_filename_trgm "
            "ON documents USING gin (filename gin_trgm_ops)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_messages_content_trgm"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_memories_value_trgm"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_documents_filename_trgm"))
