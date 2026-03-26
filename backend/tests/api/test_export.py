# backend/tests/api/test_export.py
"""Tests for the account export endpoints."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.api.export import _get_redis
from app.main import app


def _mock_redis_override(mock_redis: AsyncMock):
    """Return a dependency override that yields the given mock Redis client."""

    async def _override():
        yield mock_redis

    return _override


@pytest.mark.anyio
async def test_account_export_requires_auth(client):
    resp = await client.post("/api/export/account")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_account_export_enqueues_job(auth_client):
    """POST /api/export/account enqueues ARQ job and returns 200."""
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True  # SET NX succeeds (not in cooldown)

    app.dependency_overrides[_get_redis] = _mock_redis_override(mock_redis)
    try:
        with patch("app.api.export._enqueue_export", return_value=None):
            resp = await auth_client.post("/api/export/account")
    finally:
        app.dependency_overrides.pop(_get_redis, None)

    assert resp.status_code == 200
    assert "message" in resp.json()


@pytest.mark.anyio
async def test_account_export_cooldown(auth_client):
    """Second request within 24h returns 429 with retry_after."""
    mock_redis = AsyncMock()
    mock_redis.set.return_value = None  # SET NX fails — cooldown active
    mock_redis.ttl.return_value = 3600

    app.dependency_overrides[_get_redis] = _mock_redis_override(mock_redis)
    try:
        resp = await auth_client.post("/api/export/account")
    finally:
        app.dependency_overrides.pop(_get_redis, None)

    assert resp.status_code == 429
    body = resp.json()
    assert "retry_after" in body["detail"]


@pytest.mark.anyio
async def test_account_export_status_no_prior_export(auth_client):
    """GET status returns 200 with 'none' when no prior export."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    app.dependency_overrides[_get_redis] = _mock_redis_override(mock_redis)
    try:
        resp = await auth_client.get("/api/export/account/status")
    finally:
        app.dependency_overrides.pop(_get_redis, None)

    assert resp.status_code == 200
    assert resp.json()["status"] == "none"


@pytest.mark.anyio
async def test_account_export_status_done(auth_client):
    """GET /api/export/account/status returns done status with download_url."""
    status_data = {
        "status": "done",
        "created_at": "2026-03-26T10:00:00",
        "download_url": "https://minio.example.com/presigned",
        "expires_at": "2026-03-27T11:00:00",
    }
    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps(status_data)

    app.dependency_overrides[_get_redis] = _mock_redis_override(mock_redis)
    try:
        resp = await auth_client.get("/api/export/account/status")
    finally:
        app.dependency_overrides.pop(_get_redis, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["download_url"] == "https://minio.example.com/presigned"
