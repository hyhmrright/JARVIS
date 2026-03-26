# backend/alembic/versions/c1d2e3f4a5b6_add_search_gin_indexes.py
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
    # CREATE INDEX CONCURRENTLY must run outside a transaction block.
    # Use a fresh AUTOCOMMIT engine so Alembic's transaction is unaffected.
    # Strip asyncpg driver prefix so we get a sync psycopg2 connection.
    url = op.get_context().config.get_main_option("sqlalchemy.url")
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            conn.execute(
                sa.text(
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_content_trgm "
                    "ON messages USING gin (content gin_trgm_ops)"
                )
            )
            conn.execute(
                sa.text(
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_memories_value_trgm "
                    "ON user_memories USING gin (value gin_trgm_ops)"
                )
            )
            conn.execute(
                sa.text(
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                    "ix_documents_filename_trgm ON documents USING gin "
                    "(filename gin_trgm_ops)"
                )
            )
    finally:
        engine.dispose()


def downgrade() -> None:
    url = op.get_context().config.get_main_option("sqlalchemy.url")
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(
                sa.text("DROP INDEX CONCURRENTLY IF EXISTS ix_messages_content_trgm")
            )
            conn.execute(
                sa.text("DROP INDEX CONCURRENTLY IF EXISTS ix_memories_value_trgm")
            )
            conn.execute(
                sa.text("DROP INDEX CONCURRENTLY IF EXISTS ix_documents_filename_trgm")
            )
    finally:
        engine.dispose()
