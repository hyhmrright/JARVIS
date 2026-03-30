"""Tests for the gateway pairing endpoint."""

import pytest


@pytest.mark.anyio
async def test_pair_endpoint_requires_auth(client):
    """POST /api/gateway/pair must reject unauthenticated requests with 401."""
    resp = await client.post("/api/gateway/pair")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_pair_endpoint_method_not_allowed(client):
    """GET /api/gateway/pair should return 405 — only POST is supported."""
    resp = await client.get("/api/gateway/pair")
    assert resp.status_code == 405


@pytest.mark.anyio
async def test_pair_endpoint_exists(client):
    """POST /api/gateway/pair must not 404 — the route must be registered."""
    resp = await client.post("/api/gateway/pair")
    # 401 = route exists, auth rejected; 404 = route not registered (failure)
    assert resp.status_code != 404
