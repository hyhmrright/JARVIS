"""Tests for plugin config CRUD endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_plugins_returns_list(auth_client: AsyncClient):
    """GET /api/plugins returns list (may be empty)."""
    with patch("app.api.plugins.plugin_registry") as mock_reg:
        mock_reg.list_plugins.return_value = []
        resp = await auth_client.get("/api/plugins")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_set_plugin_config_upsert(auth_client: AsyncClient, setup_tables):
    """PUT /api/plugins/{id}/config creates or updates a config entry."""
    resp = await auth_client.put(
        "/api/plugins/test_plugin/config",
        json={"key": "api_key", "value": "secret123", "is_secret": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "api_key"
    assert data["is_secret"] is True
    assert data["value"] == "secret123"


@pytest.mark.anyio
async def test_get_plugin_config_masks_secrets(auth_client: AsyncClient, setup_tables):
    """GET /api/plugins/{id}/config masks secret values."""
    # Set a secret config
    await auth_client.put(
        "/api/plugins/test_plugin/config",
        json={"key": "token", "value": "supersecret", "is_secret": True},
    )
    # Set a non-secret config
    await auth_client.put(
        "/api/plugins/test_plugin/config",
        json={"key": "url", "value": "https://example.com", "is_secret": False},
    )
    resp = await auth_client.get("/api/plugins/test_plugin/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"]["is_secret"] is True
    assert data["token"]["value"] == "***"
    assert data["url"]["value"] == "https://example.com"


@pytest.mark.anyio
async def test_delete_plugin_config(auth_client: AsyncClient, setup_tables):
    """DELETE /api/plugins/{id}/config/{key} removes the entry."""
    await auth_client.put(
        "/api/plugins/test_plugin/config",
        json={"key": "to_delete", "value": "bye", "is_secret": False},
    )
    resp = await auth_client.delete("/api/plugins/test_plugin/config/to_delete")
    assert resp.status_code == 200
    # Verify it's gone
    cfg = await auth_client.get("/api/plugins/test_plugin/config")
    assert "to_delete" not in cfg.json()
