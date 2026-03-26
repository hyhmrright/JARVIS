"""Tests for the client error log endpoint and admin audit log endpoint."""

import pytest

# ---------------------------------------------------------------------------
# /api/logs/client-error  (no auth required)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_client_error_accepted(client):
    """Valid client error payload should return 204."""
    resp = await client.post(
        "/api/logs/client-error",
        json={
            "message": "TypeError: Cannot read properties of null",
            "source": "chat.vue",
            "url": "https://app.example.com/chat",
        },
    )
    assert resp.status_code == 204


@pytest.mark.anyio
async def test_client_error_minimal_payload(client):
    """Only 'message' is required; all other fields are optional."""
    resp = await client.post(
        "/api/logs/client-error",
        json={"message": "Something went wrong"},
    )
    assert resp.status_code == 204


@pytest.mark.anyio
async def test_client_error_message_too_long(client):
    """message exceeding max_length=500 should be rejected with 422."""
    resp = await client.post(
        "/api/logs/client-error",
        json={"message": "x" * 501},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_client_error_stack_too_long(client):
    """stack exceeding max_length=5000 should be rejected with 422."""
    resp = await client.post(
        "/api/logs/client-error",
        json={"message": "err", "stack": "s" * 5001},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /api/admin/audit-logs  (admin only)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_audit_logs_requires_admin(auth_client):
    """Non-admin user must receive 403 from the audit log endpoint."""
    resp = await auth_client.get("/api/admin/audit-logs")
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_list_audit_logs_accessible_for_admin(client, admin_auth_headers):
    """Admin user can access the audit log endpoint."""
    resp = await client.get("/api/admin/audit-logs", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.anyio
async def test_non_admin_cannot_access_admin_users(auth_client):
    """GET /api/admin/users must return 403 for non-admin users."""
    resp = await auth_client.get("/api/admin/users")
    assert resp.status_code == 403
