"""merge_heads_phase19

Revision ID: 73bcfb00a52e
Revises: c61ab334c523, ecd032398c9a
Create Date: 2026-03-26 10:17:49.316395

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "73bcfb00a52e"
down_revision: str | None = ("c61ab334c523", "ecd032398c9a")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
