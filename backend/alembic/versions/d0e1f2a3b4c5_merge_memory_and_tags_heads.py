"""merge memory and tags heads

Revision ID: d0e1f2a3b4c5
Revises: b2c3d4e5f6a1, c2d3e4f5a6b7
Create Date: 2026-03-19 20:00:00.000000

"""

from collections.abc import Sequence

revision: str = "d0e1f2a3b4c5"
down_revision: tuple[str, str] | None = ("b2c3d4e5f6a1", "c2d3e4f5a6b7")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
