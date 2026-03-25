"""add_llm_params_to_user_settings

Revision ID: 2e8ac4d05e31
Revises: e1f2a3b4c5d6
Create Date: 2026-03-24 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2e8ac4d05e31"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 添加 temperature, max_tokens, system_prompt 字段到 user_settings 表
    op.add_column(
        "user_settings",
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
    )
    op.add_column("user_settings", sa.Column("max_tokens", sa.Integer(), nullable=True))
    op.add_column("user_settings", sa.Column("system_prompt", sa.Text(), nullable=True))

    # 添加检查约束
    op.create_check_constraint(
        "ck_user_settings_temperature",
        "user_settings",
        "temperature >= 0.0 AND temperature <= 2.0",
    )
    op.create_check_constraint(
        "ck_user_settings_max_tokens",
        "user_settings",
        "max_tokens IS NULL OR max_tokens > 0",
    )


def downgrade() -> None:
    # 删除检查约束
    op.drop_constraint("ck_user_settings_max_tokens", "user_settings")
    op.drop_constraint("ck_user_settings_temperature", "user_settings")

    # 删除字段
    op.drop_column("user_settings", "system_prompt")
    op.drop_column("user_settings", "max_tokens")
    op.drop_column("user_settings", "temperature")
