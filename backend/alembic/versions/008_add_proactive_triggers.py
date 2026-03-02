"""add proactive triggers to cron jobs

Revision ID: 008
Revises: 007
Create Date: 2026-03-02 16:35:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add trigger_type column with default 'cron'
    op.add_column(
        "cron_jobs",
        sa.Column(
            "trigger_type", sa.String(length=50), nullable=False, server_default="cron"
        ),
    )
    # Add trigger_metadata JSONB column
    op.add_column(
        "cron_jobs",
        sa.Column(
            "trigger_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("cron_jobs", "trigger_metadata")
    op.drop_column("cron_jobs", "trigger_type")
