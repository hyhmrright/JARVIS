"""Add account_export_ready and account_export_failed notification types

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-03-26
"""

from __future__ import annotations

from alembic import op

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

_OLD_TYPES = (
    "'cron_completed','cron_failed','webhook_failed',"
    "'invitation_received','workflow_completed','workflow_failed'"
)
_NEW_TYPES = (
    "'cron_completed','cron_failed','webhook_failed',"
    "'invitation_received','workflow_completed','workflow_failed',"
    "'account_export_ready','account_export_failed'"
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS ck_notifications_type"
    )
    op.execute(
        "ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type "
        f"CHECK (type IN ({_NEW_TYPES}))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS ck_notifications_type"
    )
    op.execute(
        "ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type "
        f"CHECK (type IN ({_OLD_TYPES}))"
    )
