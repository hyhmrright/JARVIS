"""Tests for workspace membership and invitation endpoints."""

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Invitation


async def _setup_workspace(client: AsyncClient, auth_headers: dict) -> dict:
    """Helper: create org + workspace."""
    slug = f"inv-org-{uuid.uuid4().hex[:8]}"
    await client.post(
        "/api/organizations",
        json={"name": "Inv Org", "slug": slug},
        headers=auth_headers,
    )
    ws_resp = await client.post(
        "/api/workspaces",
        json={"name": "Inv WS"},
        headers=auth_headers,
    )
    return ws_resp.json()


def _extract_user_id_from_token(auth_headers: dict) -> uuid.UUID:
    """Extract the authenticated user's UUID from the JWT token."""
    token_str = auth_headers["Authorization"].split(" ")[1]
    payload_b64 = token_str.split(".")[1]
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    return uuid.UUID(json.loads(base64.urlsafe_b64decode(payload_b64))["sub"])


@pytest.mark.anyio
async def test_get_expired_invitation(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
) -> None:
    """Expired invitations should return 410."""
    ws_data = await _setup_workspace(client, auth_headers)
    workspace_id = uuid.UUID(ws_data["id"])
    inviter_id = _extract_user_id_from_token(auth_headers)

    inv = Invitation(
        workspace_id=workspace_id,
        inviter_id=inviter_id,
        email="x@x.com",
        role="member",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(inv)
    await db_session.flush()
    token = str(inv.token)

    resp = await client.get(f"/api/invitations/{token}")
    assert resp.status_code == 410
