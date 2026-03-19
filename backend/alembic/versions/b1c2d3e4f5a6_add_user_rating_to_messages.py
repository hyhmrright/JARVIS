"""add_user_rating_to_messages

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f7
Create Date: 2026-03-19 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("user_rating", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_messages_user_rating",
        "messages",
        "user_rating IN (-1, 1) OR user_rating IS NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_messages_user_rating", "messages", type_="check")
    op.drop_column("messages", "user_rating")
