"""Tests for Personal API Keys CRUD: POST/GET/DELETE /api/keys."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_create_key_returns_raw_key(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/keys", json={"name": "My Script", "scope": "full"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["raw_key"].startswith("jv_")
    assert len(data["raw_key"]) == 67  # "jv_" + 64 hex chars
    assert data["prefix"] == data["raw_key"][:8]
    assert data["scope"] == "full"
    assert data["name"] == "My Script"


@pytest.mark.anyio
async def test_create_readonly_key(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/keys", json={"name": "CI Token", "scope": "readonly"}
    )
    assert resp.status_code == 201
    assert resp.json()["scope"] == "readonly"


@pytest.mark.anyio
async def test_create_key_invalid_scope(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/keys", json={"name": "Bad", "scope": "superadmin"}
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_list_keys(auth_client: AsyncClient) -> None:
    await auth_client.post("/api/keys", json={"name": "Key A", "scope": "full"})
    await auth_client.post("/api/keys", json={"name": "Key B", "scope": "readonly"})
    resp = await auth_client.get("/api/keys")
    assert resp.status_code == 200
    names = [k["name"] for k in resp.json()]
    assert "Key A" in names
    assert "Key B" in names


@pytest.mark.anyio
async def test_list_keys_does_not_expose_raw_key(auth_client: AsyncClient) -> None:
    await auth_client.post("/api/keys", json={"name": "Secret", "scope": "full"})
    resp = await auth_client.get("/api/keys")
    assert resp.status_code == 200
    for key in resp.json():
        assert "raw_key" not in key
        assert "key_hash" not in key


@pytest.mark.anyio
async def test_delete_key(auth_client: AsyncClient) -> None:
    create_resp = await auth_client.post(
        "/api/keys", json={"name": "Temp", "scope": "full"}
    )
    key_id = create_resp.json()["id"]
    del_resp = await auth_client.delete(f"/api/keys/{key_id}")
    assert del_resp.status_code == 204
    list_resp = await auth_client.get("/api/keys")
    ids = [k["id"] for k in list_resp.json()]
    assert key_id not in ids


@pytest.mark.anyio
async def test_delete_nonexistent_key(auth_client: AsyncClient) -> None:
    resp = await auth_client.delete("/api/keys/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_pat_authentication(client: AsyncClient) -> None:
    """A PAT token should authenticate successfully for subsequent requests."""
    email = f"pat_{uuid.uuid4().hex[:8]}@example.com"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    create_resp = await client.post(
        "/api/keys", json={"name": "Test PAT", "scope": "full"}
    )
    assert create_resp.status_code == 201
    raw_key = create_resp.json()["raw_key"]

    client.headers["Authorization"] = f"Bearer {raw_key}"
    list_resp = await client.get("/api/keys")
    assert list_resp.status_code == 200


@pytest.mark.anyio
async def test_invalid_pat_returns_401(client: AsyncClient) -> None:
    client.headers["Authorization"] = "Bearer jv_" + "a" * 64
    resp = await client.get("/api/keys")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_max_keys_enforced(auth_client: AsyncClient) -> None:
    """Creating more than 10 keys should return 409."""
    for i in range(10):
        r = await auth_client.post(
            "/api/keys", json={"name": f"key{i}", "scope": "full"}
        )
        assert r.status_code == 201
    over_limit = await auth_client.post(
        "/api/keys", json={"name": "over", "scope": "full"}
    )
    assert over_limit.status_code == 409


@pytest.mark.anyio
async def test_cannot_delete_other_users_key(client: AsyncClient) -> None:
    """A key should not be deletable by another user."""
    # Register user A and create a key
    email_a = f"usera_{uuid.uuid4().hex[:8]}@example.com"
    reg_a = await client.post(
        "/api/auth/register",
        json={"email": email_a, "password": "password123"},
    )
    token_a = reg_a.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token_a}"
    create_resp = await client.post(
        "/api/keys", json={"name": "A key", "scope": "full"}
    )
    key_id = create_resp.json()["id"]

    # Register user B and try to delete user A's key
    email_b = f"userb_{uuid.uuid4().hex[:8]}@example.com"
    reg_b = await client.post(
        "/api/auth/register",
        json={"email": email_b, "password": "password123"},
    )
    token_b = reg_b.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token_b}"
    del_resp = await client.delete(f"/api/keys/{key_id}")
    assert del_resp.status_code == 404
