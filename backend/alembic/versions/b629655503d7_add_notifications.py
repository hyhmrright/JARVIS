"""add_notifications

Revision ID: b629655503d7
Revises: 2e8ac4d05e31
Create Date: 2026-03-24 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b629655503d7"
down_revision: str | None = "2e8ac4d05e31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 创建 notifications 表
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("action_url", sa.String(length=200), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "type IN ('cron_completed','cron_failed','webhook_failed',"
            "'invitation_received','workflow_completed','workflow_failed')",
            name="ck_notifications_type",
        ),
    )
    # 添加索引
    op.create_index(
        "ix_notifications_user_id_is_read_created_at",
        "notifications",
        ["user_id", "is_read", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notifications_user_id_is_read_created_at", table_name="notifications"
    )
    op.drop_table("notifications")
