"""Integration tests for the unified plugin install/uninstall/list endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_detect_endpoint_mcp(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get(
        "/api/plugins/detect?url=npx+%40modelcontextprotocol%2Fserver-github",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["type"] == "mcp"


@pytest.mark.anyio
async def test_detect_endpoint_skill_md(
    client: AsyncClient, auth_headers: dict
) -> None:
    response = await client.get(
        "/api/plugins/detect?url=https%3A%2F%2Fexample.com%2Fweather.md",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["type"] == "skill_md"


@pytest.mark.anyio
async def test_detect_endpoint_unrecognized(
    client: AsyncClient, auth_headers: dict
) -> None:
    response = await client.get(
        "/api/plugins/detect?url=https%3A%2F%2Fexample.com%2Fsomething",
        headers=auth_headers,
    )
    assert response.status_code == 422
    data = response.json()
    assert "candidates" in data["detail"]


@pytest.mark.anyio
async def test_install_mcp_personal(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/api/plugins/install",
        json={"url": "npx @modelcontextprotocol/server-github", "scope": "personal"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["plugin_id"] == "mcp-server-github"
    assert data["scope"] == "personal"
    assert data["type"] == "mcp"


@pytest.mark.anyio
async def test_install_mcp_duplicate_returns_409(
    client: AsyncClient, auth_headers: dict
) -> None:
    payload = {
        "url": "npx @modelcontextprotocol/server-github-dup",
        "scope": "personal",
    }
    first = await client.post(
        "/api/plugins/install", json=payload, headers=auth_headers
    )
    assert first.status_code == 200
    response = await client.post(
        "/api/plugins/install", json=payload, headers=auth_headers
    )
    assert response.status_code == 409


@pytest.mark.anyio
async def test_install_system_requires_admin(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Regular user cannot install system-scope plugin."""
    response = await client.post(
        "/api/plugins/install",
        json={"url": "npx some-pkg", "scope": "system"},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_install_system_as_admin(
    client: AsyncClient, admin_auth_headers: dict
) -> None:
    with patch(
        "app.api.plugins.reload_system_plugins", new_callable=AsyncMock
    ) as mock_reload:
        response = await client.post(
            "/api/plugins/install",
            json={"url": "npx some-admin-pkg", "scope": "system"},
            headers=admin_auth_headers,
        )
    assert response.status_code == 200
    assert response.json()["scope"] == "system"
    mock_reload.assert_awaited_once()


@pytest.mark.anyio
async def test_list_installed(client: AsyncClient, auth_headers: dict) -> None:
    # Install one personal plugin first
    await client.post(
        "/api/plugins/install",
        json={"url": "npx test-pkg-list", "scope": "personal"},
        headers=auth_headers,
    )
    response = await client.get("/api/plugins/installed", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "system" in data
    assert "personal" in data
    assert any(p["plugin_id"] == "mcp-test-pkg-list" for p in data["personal"])


@pytest.mark.anyio
async def test_uninstall_personal(client: AsyncClient, auth_headers: dict) -> None:
    install_resp = await client.post(
        "/api/plugins/install",
        json={"url": "npx pkg-to-delete", "scope": "personal"},
        headers=auth_headers,
    )
    assert install_resp.status_code == 200
    plugin_id = install_resp.json()["id"]
    response = await client.delete(
        f"/api/plugins/install/{plugin_id}", headers=auth_headers
    )
    assert response.status_code == 204


@pytest.mark.anyio
async def test_uninstall_other_user_forbidden(
    client: AsyncClient, auth_headers: dict, second_user_auth_headers: dict
) -> None:
    """User A cannot uninstall User B's personal plugin."""
    install_resp = await client.post(
        "/api/plugins/install",
        json={"url": "npx pkg-user-a", "scope": "personal"},
        headers=auth_headers,
    )
    assert install_resp.status_code == 200
    plugin_id = install_resp.json()["id"]
    response = await client.delete(
        f"/api/plugins/install/{plugin_id}", headers=second_user_auth_headers
    )
    assert response.status_code == 403
