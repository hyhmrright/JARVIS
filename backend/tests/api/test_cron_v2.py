"""Tests for new cron API endpoints: history, test trigger, quota."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.scheduler.trigger_result import TriggerResult

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


@pytest.mark.asyncio
async def test_test_trigger_agent_failure_returns_is_error(
    client: AsyncClient, auth_headers: dict
):
    """When the trigger fires but the agent raises, triggered=True and is_error=True."""
    create_resp = await client.post(
        "/api/cron",
        json={"schedule": "0 9 * * *", "task": "t", "trigger_type": "cron"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["id"]

    fired_result = TriggerResult(
        fired=True, reason="fired", trigger_ctx={"trigger_type": "cron"}
    )
    with (
        patch("app.api.cron.evaluate_trigger", AsyncMock(return_value=fired_result)),
        patch(
            "app.api.cron.run_agent_for_user",
            AsyncMock(side_effect=RuntimeError("agent down")),
        ),
    ):
        resp = await client.post(f"/api/cron/{job_id}/test", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_error"] is True
    assert body["triggered"] is True
    assert "agent down" in body["agent_result"]


@pytest.mark.asyncio
async def test_test_trigger_evaluate_failure_returns_triggered_false(
    client: AsyncClient, auth_headers: dict
):
    """When trigger evaluation itself raises, triggered=False (trigger never fired)."""
    create_resp = await client.post(
        "/api/cron",
        json={"schedule": "0 9 * * *", "task": "t", "trigger_type": "cron"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["id"]

    with patch(
        "app.api.cron.evaluate_trigger",
        AsyncMock(side_effect=RuntimeError("watcher down")),
    ):
        resp = await client.post(f"/api/cron/{job_id}/test", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_error"] is True
    assert body["triggered"] is False
    assert "watcher down" in body["agent_result"]


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


@pytest.mark.asyncio
async def test_put_cron_job_updates_task(client: AsyncClient, auth_headers: dict):
    """PUT /api/cron/{id} updates task text for owned job."""
    # Create a job first
    create_resp = await client.post(
        "/api/cron",
        json={
            "schedule": "0 9 * * *",
            "task": "original task",
            "trigger_type": "cron",
            "trigger_metadata": {},
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/cron/{job_id}",
        json={"task": "updated task"},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["id"] == job_id


@pytest.mark.asyncio
async def test_put_cron_job_404_for_other_user(client: AsyncClient, auth_headers: dict):
    """PUT /api/cron/{id} returns 404 for unowned job."""
    other_job_id = str(uuid.uuid4())
    resp = await client.put(
        f"/api/cron/{other_job_id}",
        json={"task": "new task"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_job_returns_next_run_at_in_list(
    client: AsyncClient, auth_headers: dict
):
    """After creating a job, list endpoint includes next_run_at."""
    await client.post(
        "/api/cron",
        json={
            "schedule": "0 9 * * *",
            "task": "test task",
            "trigger_type": "cron",
            "trigger_metadata": {},
        },
        headers=auth_headers,
    )
    list_resp = await client.get("/api/cron", headers=auth_headers)
    assert list_resp.status_code == 200
    jobs = list_resp.json()
    assert len(jobs) >= 1
    # next_run_at key must exist (may be None if scheduler not running in test)
    assert "next_run_at" in jobs[0]
