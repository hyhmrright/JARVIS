"""add persona_override to user_settings

Revision ID: 002
Revises: 001
Create Date: 2026-02-24

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("persona_override", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "persona_override")
