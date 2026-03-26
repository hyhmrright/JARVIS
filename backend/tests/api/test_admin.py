"""Tests for admin-only endpoints."""

import pytest


@pytest.mark.anyio
async def test_non_admin_cannot_list_users(auth_client):
    """Regular user must receive 403 when accessing admin user list."""
    resp = await auth_client.get("/api/admin/users")
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_non_admin_cannot_access_audit_logs(auth_client):
    """Regular user must receive 403 when accessing audit logs."""
    resp = await auth_client.get("/api/admin/audit-logs")
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_admin_can_list_users(client, admin_auth_headers):
    """Admin user can access the user list endpoint."""
    resp = await client.get("/api/admin/users", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
    assert "total" in data
    assert isinstance(data["users"], list)


@pytest.mark.anyio
async def test_admin_can_access_audit_logs(client, admin_auth_headers):
    """Admin user can access the audit log endpoint and get paginated results."""
    resp = await client.get("/api/admin/audit-logs", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


@pytest.mark.anyio
async def test_unauthenticated_cannot_access_admin(client):
    """Unauthenticated requests to admin endpoints must be rejected with 401 or 403."""
    resp = await client.get("/api/admin/users")
    assert resp.status_code in (401, 403)
