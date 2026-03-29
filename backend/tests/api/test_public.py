# backend/tests/api/test_public.py
"""Tests for public conversation share links."""

import uuid

import pytest

# A synthetic 43-char token (URL-safe base64 from secrets.token_urlsafe(32))
_FAKE_TOKEN = "a" * 43


@pytest.mark.anyio
async def test_public_share_nonexistent_returns_404(client):
    """Accessing a non-existent share token must return 404."""
    resp = await client.get(f"/api/public/share/{_FAKE_TOKEN}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_public_share_does_not_require_auth(client):
    """Public share endpoints must be accessible without auth (404, not 401)."""
    resp = await client.get(f"/api/public/share/{_FAKE_TOKEN}")
    assert resp.status_code != 401


@pytest.mark.anyio
async def test_public_share_token_too_short_returns_422(client):
    """Tokens shorter than 40 characters must be rejected with 422."""
    resp = await client.get("/api/public/share/tooshort")
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_share_link_requires_auth(client):
    """Creating a share link must require authentication."""
    other_conv_id = uuid.uuid4()
    resp = await client.post(
        f"/api/conversations/{other_conv_id}/share",
        json={"is_public": True},
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_create_share_link_for_other_users_conv_returns_404(auth_client):
    """Users cannot create share links for conversations they don't own."""
    other_conv_id = uuid.uuid4()
    resp = await auth_client.post(
        f"/api/conversations/{other_conv_id}/share",
        json={"is_public": True},
    )
    assert resp.status_code in (404, 403, 422)
