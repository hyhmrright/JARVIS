"""Tests for workspace membership and invitation endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.db.models import Invitation
from app.db.session import AsyncSessionLocal


@pytest.fixture(autouse=True)
def _suppress_audit():
    with patch("app.api.auth.log_action", AsyncMock(return_value=None)):
        yield


async def _setup_workspace(client: AsyncClient, auth_headers: dict) -> dict:
    """Helper: create org + workspace."""
    import uuid as _uuid

    slug = f"inv-org-{_uuid.uuid4().hex[:8]}"
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


@pytest.mark.anyio
async def test_get_expired_invitation(client: AsyncClient) -> None:
    """Expired invitations should return 410."""
    import uuid as _uuid

    async with AsyncSessionLocal() as s:
        inv = Invitation(
            workspace_id=_uuid.uuid4(),
            inviter_id=_uuid.uuid4(),
            email="x@x.com",
            role="member",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        s.add(inv)
        await s.commit()
        token = str(inv.token)

    resp = await client.get(f"/api/invitations/{token}")
    assert resp.status_code == 410
