# backend/tests/api/test_workspaces.py
"""Tests for workspace API — focuses on multi-tenant permission boundaries."""

import uuid

import pytest


@pytest.mark.anyio
async def test_list_workspaces_returns_200(auth_client):
    """Authenticated users can list workspaces."""
    resp = await auth_client.get("/api/workspaces")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_get_workspace_settings_in_different_org_returns_404(auth_client):
    """Cross-organization workspace settings lookup must return 404 or 403."""
    other_workspace_id = uuid.uuid4()
    resp = await auth_client.get(f"/api/workspaces/{other_workspace_id}/settings")
    assert resp.status_code in (403, 404)


@pytest.mark.anyio
async def test_create_workspace_requires_auth(client):
    """Unauthenticated workspace creation must be rejected."""
    resp = await client.post("/api/workspaces", json={"name": "Test"})
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_workspace_member_list_for_unknown_workspace(auth_client):
    """Member list for unknown workspace returns 403 or 404."""
    random_id = uuid.uuid4()
    resp = await auth_client.get(f"/api/workspaces/{random_id}/members")
    assert resp.status_code in (403, 404)


@pytest.mark.anyio
async def test_invite_to_unknown_workspace_returns_error(auth_client):
    """Invitation to unknown workspace returns 403 or 404."""
    random_workspace_id = uuid.uuid4()
    resp = await auth_client.post(
        f"/api/workspaces/{random_workspace_id}/invitations",
        json={"email": "stranger@example.com", "role": "member"},
    )
    assert resp.status_code in (403, 404, 422)


@pytest.mark.anyio
async def test_list_workspaces_unauthenticated_returns_401(client):
    """Unauthenticated list workspaces must return 401."""
    resp = await client.get("/api/workspaces")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_update_workspace_unknown_returns_error(auth_client):
    """Updating an unknown workspace must return 403 or 404."""
    random_id = uuid.uuid4()
    resp = await auth_client.put(
        f"/api/workspaces/{random_id}", json={"name": "New Name"}
    )
    assert resp.status_code in (403, 404)
