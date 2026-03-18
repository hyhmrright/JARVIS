"""merge_active_leaf_and_share_token_heads

Revision ID: c7c0b68bab0e
Revises: 6b20ba595a05, a1b2c3d4e5f6
Create Date: 2026-03-17 18:19:43.096224

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c7c0b68bab0e"
down_revision: str | None = ("6b20ba595a05", "a1b2c3d4e5f6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
