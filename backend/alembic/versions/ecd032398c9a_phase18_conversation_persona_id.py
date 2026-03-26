"""phase18_conversation_persona_id

Revision ID: ecd032398c9a
Revises: 89ffae495641
Create Date: 2026-03-26 09:30:29.314525

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ecd032398c9a"
down_revision: str | None = "89ffae495641"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("persona_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_persona_id",
        "conversations",
        "personas",
        ["persona_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_conversations_persona_id", "conversations", type_="foreignkey"
    )
    op.drop_column("conversations", "persona_id")
