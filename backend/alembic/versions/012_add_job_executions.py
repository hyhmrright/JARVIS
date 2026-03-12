"""add job_executions table

Revision ID: 012
Revises: 011
Create Date: 2026-03-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_executions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cron_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_group_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "fired_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("trigger_ctx", JSONB, nullable=True),
        sa.Column("agent_result", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("attempt", sa.SmallInteger, server_default="1", nullable=False),
    )
    op.create_index("idx_job_executions_job_id", "job_executions", ["job_id"])
    op.create_index(
        "idx_job_executions_fired_at",
        "job_executions",
        ["fired_at"],
        postgresql_ops={"fired_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_job_executions_fired_at", table_name="job_executions")
    op.drop_index("idx_job_executions_job_id", table_name="job_executions")
    op.drop_table("job_executions")
