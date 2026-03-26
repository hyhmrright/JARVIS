"""phase18_persona_fields

Revision ID: 89ffae495641
Revises: d7364c743e28
Create Date: 2026-03-26 09:21:05.052401

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "89ffae495641"
down_revision: str | None = "d7364c743e28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("personas", sa.Column("temperature", sa.Float(), nullable=True))
    op.add_column(
        "personas", sa.Column("model_name", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "personas",
        sa.Column(
            "enabled_tools",
            postgresql.ARRAY(sa.String()),
            nullable=True,
        ),
    )
    op.add_column(
        "personas",
        sa.Column(
            "replace_system_prompt",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("personas", "replace_system_prompt")
    op.drop_column("personas", "enabled_tools")
    op.drop_column("personas", "model_name")
    op.drop_column("personas", "temperature")
