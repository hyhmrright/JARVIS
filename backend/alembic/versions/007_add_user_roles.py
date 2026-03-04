"""add user roles

Revision ID: 007
Revises: 006
Create Date: 2026-03-02 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add role column to users table with default value 'user'
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
