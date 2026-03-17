# backend/tests/api/test_workspace_permissions.py
"""Security test: non-members must not access workspace-scoped resources."""

import base64
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def _register(client: AsyncClient, suffix: str = "") -> str:
    """Register a unique user and return their JWT token."""
    email = f"user_{uuid.uuid4().hex[:8]}{suffix}@test.com"
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def _create_org_and_workspace(client: AsyncClient, token: str) -> str:
    """Create an org + workspace as the given user. Returns workspace_id."""
    client.headers["Authorization"] = f"Bearer {token}"
    slug = f"org-{uuid.uuid4().hex[:8]}"
    org = await client.post(
        "/api/organizations",
        json={"name": f"Org-{uuid.uuid4().hex[:4]}", "slug": slug},
    )
    assert org.status_code == 201, org.text
    ws = await client.post(
        "/api/workspaces",
        json={"name": f"WS-{uuid.uuid4().hex[:4]}"},
    )
    assert ws.status_code == 201, ws.text
    return ws.json()["id"]


def _user_id_from_token(token: str) -> uuid.UUID:
    """Extract user UUID from JWT payload without verifying signature."""
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    return uuid.UUID(json.loads(base64.urlsafe_b64decode(payload_b64))["sub"])


@pytest.mark.anyio
async def test_cross_org_user_cannot_list_workspace_cron_jobs(client: AsyncClient) -> None:
    """GET /api/cron?workspace_id=<ws> must return 404 for cross-org users.

    Users with no organization (organization_id=None) are treated as cross-org
    and receive 404 to avoid leaking workspace existence across organizations.
    """
    token_a = await _register(client, "_a")
    workspace_id = await _create_org_and_workspace(client, token_a)

    # User B has no organization (organization_id=None → cross-org → 404)
    token_b = await _register(client, "_b")
    client.headers["Authorization"] = f"Bearer {token_b}"

    resp = await client.get(f"/api/cron?workspace_id={workspace_id}")
    assert resp.status_code == 404, (
        f"Expected 404, got {resp.status_code}. "
        "Users outside the workspace's organization must receive 404."
    )


@pytest.mark.anyio
async def test_same_org_non_member_cannot_list_workspace_cron_jobs(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /api/cron?workspace_id=<ws> must return 403 for same-org non-members.

    A user who belongs to the same organization but is not a member of the
    specific workspace must receive 403 (not 404, because the workspace exists
    and is visible within their organization).
    """
    token_a = await _register(client, "_a")
    workspace_id = await _create_org_and_workspace(client, token_a)

    # Get User A's organization ID
    client.headers["Authorization"] = f"Bearer {token_a}"
    org_resp = await client.get("/api/organizations/me")
    assert org_resp.status_code == 200, org_resp.text
    org_id = uuid.UUID(org_resp.json()["id"])

    # Register User B, then place them in User A's org but NOT in the workspace
    token_b = await _register(client, "_b")
    user_b_id = _user_id_from_token(token_b)
    user_b = await db_session.get(User, user_b_id)
    assert user_b is not None
    user_b.organization_id = org_id
    await db_session.flush()

    # User B is in the same org but is not a workspace member → 403
    client.headers["Authorization"] = f"Bearer {token_b}"
    resp = await client.get(f"/api/cron?workspace_id={workspace_id}")
    assert resp.status_code == 403, (
        f"Expected 403, got {resp.status_code}. "
        "Same-org users who are not workspace members must be blocked with 403."
    )


@pytest.mark.anyio
async def test_nonexistent_workspace_returns_404(client: AsyncClient) -> None:
    """GET /api/cron?workspace_id=<random-uuid> must return 404."""
    token = await _register(client, "_c")
    client.headers["Authorization"] = f"Bearer {token}"

    nonexistent_id = str(uuid.uuid4())
    resp = await client.get(f"/api/cron?workspace_id={nonexistent_id}")
    assert resp.status_code == 404, (
        f"Expected 404, got {resp.status_code}. "
        "Non-existent workspace must return 404, not 403."
    )
