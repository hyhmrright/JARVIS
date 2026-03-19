"""add composite indexes for common query patterns

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-03-19 20:05:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Messages: speed up conversation history queries ordered by time
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_messages_conversation_created "
        "ON messages(conversation_id, created_at DESC)"
    )
    # Messages: speed up search queries filtering by role
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_messages_conversation_role_created "
        "ON messages(conversation_id, role, created_at DESC)"
    )
    # Audit logs: speed up admin log filtering by action + user
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_action_user_created "
        "ON audit_logs(action, user_id, created_at DESC)"
    )
    # Documents: speed up workspace document listing (excluding soft-deleted)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_workspace_deleted_created "
        "ON documents(workspace_id, is_deleted, created_at DESC)"
    )
    # Conversations: speed up user conversation listing ordered by time
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversations_user_created "
        "ON conversations(user_id, created_at DESC)"
    )
    # Conversations: speed up workspace conversation listing
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversations_workspace_created "
        "ON conversations(workspace_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_conversations_workspace_created")
    op.execute("DROP INDEX IF EXISTS ix_conversations_user_created")
    op.execute("DROP INDEX IF EXISTS ix_documents_workspace_deleted_created")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_action_user_created")
    op.execute("DROP INDEX IF EXISTS ix_messages_conversation_role_created")
    op.execute("DROP INDEX IF EXISTS ix_messages_conversation_created")
