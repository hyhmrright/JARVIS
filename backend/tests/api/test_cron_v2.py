"""Tests for new cron API endpoints: history, test trigger, quota."""

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient

# --- GET /api/cron/{job_id}/history ---


@pytest.mark.asyncio
async def test_history_404_for_other_user_job(client: AsyncClient, auth_headers: dict):
    """History endpoint returns 404 for jobs not owned by current user."""
    other_job_id = str(uuid.uuid4())
    response = await client.get(
        f"/api/cron/{other_job_id}/history",
        headers=auth_headers,
    )
    assert response.status_code == 404


# --- POST /api/cron/{job_id}/test ---


@pytest.mark.asyncio
async def test_test_endpoint_404_for_other_user_job(
    client: AsyncClient, auth_headers: dict
):
    """Test endpoint returns 404 for unowned jobs."""
    other_job_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/cron/{other_job_id}/test",
        headers=auth_headers,
    )
    assert response.status_code == 404


# --- POST /api/cron quota ---


@pytest.mark.asyncio
async def test_create_job_quota_exceeded(client: AsyncClient, auth_headers: dict):
    """Creating more than MAX_CRON_JOBS_PER_USER active jobs returns 429."""
    with patch("app.api.cron.settings") as mock_settings:
        mock_settings.max_cron_jobs_per_user = 0
        response = await client.post(
            "/api/cron",
            json={
                "schedule": "0 9 * * *",
                "task": "test",
                "trigger_type": "cron",
                "trigger_metadata": {},
            },
            headers=auth_headers,
        )
    assert response.status_code == 429
