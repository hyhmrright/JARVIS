"""Tests for organization and workspace CRUD endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _suppress_audit():
    with patch("app.api.auth.log_action", AsyncMock(return_value=None)):
        yield


@pytest.mark.anyio
async def test_create_organization(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        "/api/organizations",
        json={"name": "Test Org", "slug": "test-org"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "test-org"
    assert data["name"] == "Test Org"


@pytest.mark.anyio
async def test_create_organization_duplicate_slug(
    client: AsyncClient, auth_headers: dict
) -> None:
    await client.post(
        "/api/organizations",
        json={"name": "Org A", "slug": "slug-clash"},
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/organizations",
        json={"name": "Org B", "slug": "slug-clash"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_get_my_organization(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/api/organizations",
        json={"name": "My Org", "slug": "my-org-x"},
        headers=auth_headers,
    )
    resp = await client.get("/api/organizations/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["slug"] == "my-org-x"


@pytest.mark.anyio
async def test_get_my_organization_no_org(
    client: AsyncClient, auth_headers: dict
) -> None:
    resp = await client.get("/api/organizations/me", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_create_workspace(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/api/organizations",
        json={"name": "WS Org", "slug": "ws-org"},
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/workspaces",
        json={"name": "Engineering"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Engineering"


@pytest.mark.anyio
async def test_list_workspaces(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/api/organizations",
        json={"name": "List Org", "slug": "list-org"},
        headers=auth_headers,
    )
    await client.post("/api/workspaces", json={"name": "Alpha"}, headers=auth_headers)
    await client.post("/api/workspaces", json={"name": "Beta"}, headers=auth_headers)
    resp = await client.get("/api/workspaces", headers=auth_headers)
    assert resp.status_code == 200
    names = [w["name"] for w in resp.json()]
    assert "Alpha" in names and "Beta" in names


@pytest.mark.anyio
async def test_delete_workspace_soft(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/api/organizations",
        json={"name": "Del Org", "slug": "del-org"},
        headers=auth_headers,
    )
    create = await client.post(
        "/api/workspaces", json={"name": "ToDelete"}, headers=auth_headers
    )
    ws_id = create.json()["id"]
    del_resp = await client.delete(f"/api/workspaces/{ws_id}", headers=auth_headers)
    assert del_resp.status_code == 204
    list_resp = await client.get("/api/workspaces", headers=auth_headers)
    ids = [w["id"] for w in list_resp.json()]
    assert ws_id not in ids
