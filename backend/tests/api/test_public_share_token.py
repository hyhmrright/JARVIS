"""Tests for public share token security (opaque token, not UUID primary key)."""

import re
import uuid

import pytest


async def test_share_token_is_opaque_not_uuid(auth_client):
    """Share token must be an opaque random string, not a UUID primary key."""
    resp = await auth_client.post("/api/conversations", json={"title": "Token Test"})
    assert resp.status_code == 201
    conv_id = resp.json()["id"]

    resp = await auth_client.post(f"/api/conversations/{conv_id}/share")
    assert resp.status_code == 200
    token = resp.json()["token"]

    # Token must NOT be a UUID (predictable internal key)
    with pytest.raises(ValueError):
        uuid.UUID(token)

    # Token must be a URL-safe base64 string (secrets.token_urlsafe format)
    assert re.fullmatch(r"[A-Za-z0-9_\-]{40,}", token), (
        f"Expected opaque URL-safe token, got: {token!r}"
    )


async def test_share_token_idempotent(auth_client):
    """Sharing the same conversation twice returns the same token."""
    resp = await auth_client.post(
        "/api/conversations", json={"title": "Idempotent Test"}
    )
    conv_id = resp.json()["id"]

    r1 = await auth_client.post(f"/api/conversations/{conv_id}/share")
    r2 = await auth_client.post(f"/api/conversations/{conv_id}/share")
    assert r1.json()["token"] == r2.json()["token"]


async def test_public_endpoint_accepts_opaque_token(auth_client, client):
    """GET /api/public/share/{token} works with opaque share token."""
    resp = await auth_client.post(
        "/api/conversations", json={"title": "Public Share Test"}
    )
    conv_id = resp.json()["id"]

    share_resp = await auth_client.post(f"/api/conversations/{conv_id}/share")
    token = share_resp.json()["token"]

    pub_resp = await client.get(f"/api/public/share/{token}")
    assert pub_resp.status_code == 200
    data = pub_resp.json()
    assert data["title"] == "Public Share Test"
    assert isinstance(data["messages"], list)


async def test_public_endpoint_rejects_invalid_token(client):
    """GET /api/public/share/{token} returns 404 for valid-format but unknown token."""
    # Use a properly-formatted token that passes length validation but doesn't exist.
    unknown_token = "A" * 43
    resp = await client.get(f"/api/public/share/{unknown_token}")
    assert resp.status_code == 404


async def test_public_endpoint_rejects_too_short_token(client):
    """GET /api/public/share/{token} returns 422 for tokens shorter than min_length."""
    resp = await client.get("/api/public/share/short")
    assert resp.status_code == 422


async def test_public_endpoint_rejects_uuid_format_token(client):
    """GET /api/public/share/{token} returns 422 for a UUID-format token (old format).

    UUID strings are 36 chars — below the min_length=40 constraint — so old
    UUID-format share links are rejected with a validation error, not a 404.
    """
    random_uuid = str(uuid.uuid4())
    assert len(random_uuid) == 36  # sanity check: UUID is 36 chars < min_length=40
    resp = await client.get(f"/api/public/share/{random_uuid}")
    assert resp.status_code == 422
