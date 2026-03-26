"""merge_phase19_webhook_and_phase21_export_heads

Revision ID: 3e2598640e52
Revises: 7167dd772125, d2e3f4a5b6c7
Create Date: 2026-03-26 21:27:03.182632

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "3e2598640e52"
down_revision: str | None = ("7167dd772125", "d2e3f4a5b6c7")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
