"""add_workflow_runs

Revision ID: 3c2651fd98a3
Revises: b629655503d7
Create Date: 2026-03-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c2651fd98a3"
down_revision: str | None = "b629655503d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 创建 workflow_runs 表
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "input_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "output_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "run_log",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed')",
            name="ck_workflow_runs_status",
        ),
    )
    op.create_index("ix_workflow_runs_user_id", "workflow_runs", ["user_id"])
    op.create_index("ix_workflow_runs_workflow_id", "workflow_runs", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_runs_workflow_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_user_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")
