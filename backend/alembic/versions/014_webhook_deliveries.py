"""add webhook_deliveries table

Revision ID: 014
Revises: 013
Create Date: 2026-03-13
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "webhook_id",
            UUID(as_uuid=True),
            sa.ForeignKey("webhooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("response_code", sa.Integer, nullable=True),
        sa.Column("response_body", sa.Text, nullable=True),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'success', 'failed')",
            name="ck_webhook_deliveries_status",
        ),
    )
    op.create_index(
        "idx_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"]
    )
    op.create_index(
        "idx_webhook_deliveries_triggered_at",
        "webhook_deliveries",
        [sa.text("triggered_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_webhook_deliveries_triggered_at", table_name="webhook_deliveries"
    )
    op.drop_index("idx_webhook_deliveries_webhook_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
