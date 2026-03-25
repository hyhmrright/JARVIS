"""phase16_indexes_and_webhook_encryption

Revision ID: d7364c743e28
Revises: 3c2651fd98a3
Create Date: 2026-03-25 21:20:35.768329

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7364c743e28"
down_revision: str | None = "3c2651fd98a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Add missing indexes ---
    op.create_index("ix_personas_user_id", "personas", ["user_id"])
    op.create_index("ix_workflows_user_id", "workflows", ["user_id"])
    op.create_index(
        "ix_installed_plugins_installed_by", "installed_plugins", ["installed_by"]
    )

    # --- Widen secret_token column for Fernet-encrypted values ---
    op.alter_column(
        "webhooks",
        "secret_token",
        type_=sa.String(500),
        existing_type=sa.String(255),
        existing_nullable=False,
    )

    # --- Batch-encrypt existing plaintext webhook secrets ---
    conn = op.get_bind()
    rows = conn.execute(text("SELECT id, secret_token FROM webhooks")).fetchall()
    if rows:
        from app.core.security import fernet_encrypt

        for row in rows:
            # Skip rows already Fernet-encrypted (tokens start with "gAAAAA")
            if row.secret_token.startswith("gAAAAA"):
                continue
            encrypted = fernet_encrypt(row.secret_token)
            conn.execute(
                text("UPDATE webhooks SET secret_token = :token WHERE id = :id"),
                {"token": encrypted, "id": row.id},
            )


def downgrade() -> None:
    # --- Batch-decrypt webhook secrets back to plaintext ---
    from cryptography.fernet import InvalidToken

    conn = op.get_bind()
    rows = conn.execute(text("SELECT id, secret_token FROM webhooks")).fetchall()
    if rows:
        from app.core.security import fernet_decrypt

        for row in rows:
            try:
                decrypted = fernet_decrypt(row.secret_token)
                conn.execute(
                    text("UPDATE webhooks SET secret_token = :token WHERE id = :id"),
                    {"token": decrypted, "id": row.id},
                )
            except InvalidToken:
                pass  # Already plaintext or unrecognised format — leave as-is

    op.alter_column(
        "webhooks",
        "secret_token",
        type_=sa.String(255),
        existing_type=sa.String(500),
        existing_nullable=False,
    )

    op.drop_index("ix_installed_plugins_installed_by", "installed_plugins")
    op.drop_index("ix_workflows_user_id", "workflows")
    op.drop_index("ix_personas_user_id", "personas")
