"""Tests for webhook trigger endpoints."""

import uuid
from unittest.mock import AsyncMock, patch


async def test_create_webhook(auth_client):
    """POST /api/webhooks creates a webhook and returns secret_token."""
    resp = await auth_client.post(
        "/api/webhooks",
        json={
            "name": "GitHub Events",
            "task_template": "Process GitHub event: {payload}",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "GitHub Events"
    assert data["task_template"] == "Process GitHub event: {payload}"
    assert "secret_token" in data
    assert len(data["secret_token"]) > 0
    # Verify returned secret is NOT Fernet-formatted (should be plaintext)
    assert not data["secret_token"].startswith("gAAAAA")
    assert data["trigger_count"] == 0
    assert data["is_active"] is True
    assert data["last_triggered_at"] is None


async def test_list_webhooks(auth_client):
    """GET /api/webhooks returns all active webhooks for the current user."""
    await auth_client.post(
        "/api/webhooks",
        json={"name": "Hook 1", "task_template": "Task 1: {payload}"},
    )
    await auth_client.post(
        "/api/webhooks",
        json={"name": "Hook 2", "task_template": "Task 2: {payload}"},
    )
    resp = await auth_client.get("/api/webhooks")
    assert resp.status_code == 200
    webhooks = resp.json()
    names = [w["name"] for w in webhooks]
    assert "Hook 1" in names
    assert "Hook 2" in names
    # Verify all secrets are masked in list responses
    assert all(w["secret_token"] == "••••••••" for w in webhooks)


async def test_delete_webhook(auth_client):
    """DELETE /api/webhooks/{id} soft-deletes (returns 204) and hides from listing."""
    create = await auth_client.post(
        "/api/webhooks",
        json={"name": "To Delete", "task_template": "Delete me: {payload}"},
    )
    assert create.status_code == 201
    webhook_id = create.json()["id"]

    resp = await auth_client.delete(f"/api/webhooks/{webhook_id}")
    assert resp.status_code == 204

    # Soft-deleted webhook should not appear in list
    list_resp = await auth_client.get("/api/webhooks")
    assert list_resp.status_code == 200
    ids = [w["id"] for w in list_resp.json()]
    assert webhook_id not in ids


async def test_trigger_webhook_valid_secret(auth_client):
    """POST /trigger with correct secret returns 202 and task_preview."""
    create = await auth_client.post(
        "/api/webhooks",
        json={
            "name": "Zapier Hook",
            "task_template": "Handle Zapier event: {payload}",
        },
    )
    data = create.json()
    webhook_id = data["id"]
    secret = data["secret_token"]

    # Trigger without authentication token (secret IS the auth)
    auth_client.headers.pop("Authorization", None)
    resp = await auth_client.post(
        f"/api/webhooks/{webhook_id}/trigger",
        json={"event": "push", "ref": "refs/heads/main"},
        headers={"X-Webhook-Secret": secret},
    )
    assert resp.status_code == 202
    result = resp.json()
    assert result["status"] == "accepted"
    assert "task_preview" in result


async def test_trigger_webhook_invalid_secret(auth_client):
    """POST /trigger with wrong secret returns 401."""
    create = await auth_client.post(
        "/api/webhooks",
        json={"name": "Secret Hook", "task_template": "Task: {payload}"},
    )
    webhook_id = create.json()["id"]

    auth_client.headers.pop("Authorization", None)
    resp = await auth_client.post(
        f"/api/webhooks/{webhook_id}/trigger",
        json={"data": "test"},
        headers={"X-Webhook-Secret": "wrong-secret"},
    )
    assert resp.status_code == 401


async def test_trigger_webhook_not_found(auth_client):
    """POST /trigger for a nonexistent webhook_id returns 404."""
    nonexistent_id = str(uuid.uuid4())
    auth_client.headers.pop("Authorization", None)
    resp = await auth_client.post(
        f"/api/webhooks/{nonexistent_id}/trigger",
        json={},
        headers={"X-Webhook-Secret": "any-secret"},
    )
    assert resp.status_code == 404


async def test_trigger_increments_count(auth_client):
    """Successful trigger increments trigger_count and sets last_triggered_at."""
    create = await auth_client.post(
        "/api/webhooks",
        json={"name": "Counter Hook", "task_template": "Count: {payload}"},
    )
    data = create.json()
    webhook_id = data["id"]
    secret = data["secret_token"]
    # Re-auth to check listing after trigger
    auth_header = auth_client.headers.get("Authorization")

    auth_client.headers.pop("Authorization", None)
    resp = await auth_client.post(
        f"/api/webhooks/{webhook_id}/trigger",
        json={},
        headers={"X-Webhook-Secret": secret},
    )
    assert resp.status_code == 202

    # Restore auth to check listing
    auth_client.headers["Authorization"] = auth_header
    list_resp = await auth_client.get("/api/webhooks")
    hooks = {w["id"]: w for w in list_resp.json()}
    assert hooks[webhook_id]["trigger_count"] == 1
    assert hooks[webhook_id]["last_triggered_at"] is not None


async def test_trigger_webhook_wrong_user_cannot_delete(client):
    """User A cannot delete User B's webhook."""
    # Register user A
    resp_a = await client.post(
        "/api/auth/register",
        json={"email": "user_a@example.com", "password": "password123"},
    )
    token_a = resp_a.json()["access_token"]

    # User A creates a webhook
    client.headers["Authorization"] = f"Bearer {token_a}"
    create = await client.post(
        "/api/webhooks",
        json={"name": "User A Hook", "task_template": "A: {payload}"},
    )
    webhook_id = create.json()["id"]

    # Register user B
    resp_b = await client.post(
        "/api/auth/register",
        json={"email": "user_b@example.com", "password": "password123"},
    )
    token_b = resp_b.json()["access_token"]

    # User B tries to delete user A's webhook
    client.headers["Authorization"] = f"Bearer {token_b}"
    resp = await client.delete(f"/api/webhooks/{webhook_id}")
    assert resp.status_code == 404


async def test_trigger_webhook_malformed_json_logs_debug(auth_client):
    """Malformed JSON body must be logged at debug level, not silently discarded.

    FAILS before fix: except Exception swallows the parse error without logging.
    PASSES after fix: logger.debug("webhook_json_parse_failed", error=...) is called.
    """
    create = await auth_client.post(
        "/api/webhooks",
        json={"name": "JSON Test Hook", "task_template": "Task: {payload}"},
    )
    webhook_id = create.json()["id"]
    secret = create.json()["secret_token"]
    auth_client.headers.pop("Authorization", None)

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()
    mock_pool.aclose = AsyncMock()

    with patch("app.api.webhooks.create_pool", return_value=mock_pool):
        with patch("app.api.webhooks.logger") as mock_logger:
            resp = await auth_client.post(
                f"/api/webhooks/{webhook_id}/trigger",
                content=b"not-valid-json!!!",
                headers={
                    "X-Webhook-Secret": secret,
                    "Content-Type": "application/json",
                },
            )

    assert resp.status_code == 202
    # Verify debug log was called for JSON parse failure
    debug_calls = [
        call
        for call in mock_logger.debug.call_args_list
        if call.args and call.args[0] == "webhook_json_parse_failed"
    ]
    assert len(debug_calls) == 1, (
        f"Expected exactly one 'webhook_json_parse_failed' debug log; "
        f"all debug calls: {mock_logger.debug.call_args_list}"
    )
    assert "error" in debug_calls[0].kwargs, (
        "webhook_json_parse_failed log must include error= kwarg"
    )
