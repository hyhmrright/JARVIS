# backend/tests/api/test_export.py
"""Tests for the account export endpoints."""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import decode_access_token


def _uid(auth_client) -> uuid.UUID:
    token = auth_client.headers["Authorization"].split(" ")[1]
    return uuid.UUID(decode_access_token(token))


@pytest.mark.anyio
async def test_account_export_requires_auth(client):
    resp = await client.post("/api/export/account")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_account_export_enqueues_job(auth_client):
    """POST /api/export/account enqueues ARQ job and returns 200."""
    with (
        patch("app.api.export._get_redis_client") as mock_redis_fn,
        patch("app.api.export._enqueue_export") as mock_enqueue,
    ):
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True  # SET NX succeeds (not in cooldown)
        mock_redis_fn.return_value = mock_redis
        mock_enqueue.return_value = None

        resp = await auth_client.post("/api/export/account")
        assert resp.status_code == 200
        assert "message" in resp.json()


@pytest.mark.anyio
async def test_account_export_cooldown(auth_client):
    """Second request within 24h returns 429 with retry_after."""
    with patch("app.api.export._get_redis_client") as mock_redis_fn:
        mock_redis = AsyncMock()
        # SET NX fails — key already exists (cooldown active)
        mock_redis.set.return_value = None
        mock_redis.ttl.return_value = 3600  # 1 hour remaining
        mock_redis_fn.return_value = mock_redis

        resp = await auth_client.post("/api/export/account")
        assert resp.status_code == 429
        body = resp.json()
        assert "retry_after" in body["detail"] or "retry_after" in body


@pytest.mark.anyio
async def test_account_export_status_no_prior_export(auth_client):
    """GET status returns 200 with 'none' when no prior export."""
    with patch("app.api.export._get_redis_client") as mock_redis_fn:
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # no status key
        mock_redis_fn.return_value = mock_redis

        resp = await auth_client.get("/api/export/account/status")
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
    with patch("app.api.export._get_redis_client") as mock_redis_fn:
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(status_data)
        mock_redis_fn.return_value = mock_redis

        resp = await auth_client.get("/api/export/account/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "done"
        assert body["download_url"] == "https://minio.example.com/presigned"
