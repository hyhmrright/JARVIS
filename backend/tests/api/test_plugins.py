# backend/tests/api/test_plugins.py
"""Tests for plugin API — permission boundaries and detect_type helper."""

import pytest


@pytest.mark.anyio
async def test_list_plugins_requires_auth(client):
    """Unauthenticated plugin list must return 401."""
    resp = await client.get("/api/plugins")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_list_installed_plugins_requires_auth(client):
    """Unauthenticated installed plugin list must return 401."""
    resp = await client.get("/api/plugins/installed")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_list_installed_plugins_returns_200(auth_client):
    """Authenticated users can list installed plugins (grouped by scope)."""
    resp = await auth_client.get("/api/plugins/installed")
    assert resp.status_code == 200
    data = resp.json()
    # Response is grouped: {"personal": [...], "system": [...]}
    assert isinstance(data, dict)
    assert "personal" in data
    assert "system" in data


@pytest.mark.anyio
async def test_install_plugin_requires_auth(client):
    """Unauthenticated plugin install must return 401."""
    resp = await client.post(
        "/api/plugins/install",
        json={"url": "https://example.com/plugin", "scope": "personal"},
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_detect_plugin_type_requires_auth(client):
    """detect_plugin_type endpoint must require authentication."""
    resp = await client.get("/api/plugins/detect?url=https://example.com/plugin")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_detect_plugin_type_unrecognized_url_returns_422(auth_client):
    """detect_plugin_type with an unrecognizable URL returns 422."""
    resp = await auth_client.get(
        "/api/plugins/detect?url=https://example.com/totally-unknown"
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_list_market_skills_requires_auth(client):
    """Unauthenticated market skills list must return 401."""
    resp = await client.get("/api/plugins/market/skills")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_list_plugins_returns_200(auth_client):
    """Authenticated users can list plugins."""
    resp = await auth_client.get("/api/plugins")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
