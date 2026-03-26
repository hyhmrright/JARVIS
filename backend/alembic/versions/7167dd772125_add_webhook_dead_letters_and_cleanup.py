"""add_webhook_dead_letters_and_cleanup

Revision ID: 7167dd772125
Revises: 73bcfb00a52e
Create Date: 2026-03-26 10:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7167dd772125"
down_revision: str | None = "73bcfb00a52e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhook_dead_letters",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "webhook_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("webhooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_webhook_dead_letters_webhook_id",
        "webhook_dead_letters",
        ["webhook_id"],
    )
    op.create_index(
        "ix_webhook_dead_letters_user_id",
        "webhook_dead_letters",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_dead_letters_user_id", table_name="webhook_dead_letters")
    op.drop_index(
        "ix_webhook_dead_letters_webhook_id", table_name="webhook_dead_letters"
    )
    op.drop_table("webhook_dead_letters")
