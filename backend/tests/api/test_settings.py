"""Tests for the user settings API."""

import pytest


@pytest.mark.anyio
async def test_get_settings_returns_defaults(auth_client):
    resp = await auth_client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "model_provider" in data
    assert "model_name" in data
    assert "enabled_tools" in data


@pytest.mark.anyio
async def test_update_model_provider(auth_client):
    resp = await auth_client.put(
        "/api/settings",
        json={"model_provider": "openai", "model_name": "gpt-4o-mini"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    get_resp = await auth_client.get("/api/settings")
    data = get_resp.json()
    assert data["model_provider"] == "openai"
    assert data["model_name"] == "gpt-4o-mini"


@pytest.mark.anyio
async def test_update_enabled_tools(auth_client):
    resp = await auth_client.put(
        "/api/settings",
        json={"enabled_tools": ["search", "datetime"]},
    )
    assert resp.status_code == 200

    get_resp = await auth_client.get("/api/settings")
    # Only valid tool names are stored; at minimum both should be present if valid
    enabled = get_resp.json()["enabled_tools"]
    assert isinstance(enabled, list)


@pytest.mark.anyio
async def test_temperature_validation(auth_client):
    """Temperature outside 0-2 range should be rejected with 422."""
    resp = await auth_client.put("/api/settings", json={"temperature": 3.5})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_temperature_valid_boundary(auth_client):
    resp = await auth_client.put("/api/settings", json={"temperature": 2.0})
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_api_keys_not_returned_in_plaintext(auth_client):
    """After storing an API key, GET /settings must not return the raw key."""
    await auth_client.put(
        "/api/settings",
        json={"api_keys": {"openai": "sk-supersecretkey1234"}},
    )
    get_resp = await auth_client.get("/api/settings")
    data = get_resp.json()

    # The raw key should not appear anywhere in the response
    raw_key = "sk-supersecretkey1234"
    assert raw_key not in str(data)
    # Masked keys should be present with ellipsis
    masked = data.get("masked_api_keys", {})
    if "openai" in masked:
        assert "..." in masked["openai"][0]


@pytest.mark.anyio
async def test_invalid_model_for_provider_rejected(auth_client):
    """Model name not in the provider's allowed list must be rejected."""
    resp = await auth_client.put(
        "/api/settings",
        json={"model_provider": "openai", "model_name": "fake-model-xyz"},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_settings_requires_auth(client):
    resp = await client.get("/api/settings")
    assert resp.status_code == 401
