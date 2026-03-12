import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scheduler.runner import _execute_cron_job


@pytest.mark.asyncio
async def test_execute_cron_job_enqueues_arq_job():
    """_execute_cron_job enqueues the job to ARQ pool when pool is initialized."""
    job_id = str(uuid.uuid4())

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()

    with patch("app.scheduler.runner._arq_pool", mock_pool):
        await _execute_cron_job(job_id)

    mock_pool.enqueue_job.assert_awaited_once()
    call_kwargs = mock_pool.enqueue_job.call_args
    assert call_kwargs.args[0] == "execute_cron_job"
    assert call_kwargs.kwargs["job_id"] == job_id
    assert "run_group_id" in call_kwargs.kwargs


@pytest.mark.asyncio
async def test_execute_cron_job_skips_when_pool_not_initialized():
    """_execute_cron_job logs error and returns early when ARQ pool is not set."""
    with patch("app.scheduler.runner._arq_pool", None):
        # Should return without raising
        await _execute_cron_job(str(uuid.uuid4()))
