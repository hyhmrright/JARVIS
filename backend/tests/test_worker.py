import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scheduler.trigger_result import TriggerResult


@pytest.mark.asyncio
async def test_execute_cron_job_fires_agent():
    """When trigger fires, agent is invoked and execution is recorded."""
    job_id = str(uuid.uuid4())
    run_group_id = str(uuid.uuid4())

    mock_job = MagicMock()
    mock_job.id = uuid.UUID(job_id)
    mock_job.user_id = uuid.uuid4()
    mock_job.task = "Check prices"
    mock_job.trigger_type = "cron"
    mock_job.trigger_metadata = {}
    mock_job.is_active = True

    fired_result = TriggerResult(
        fired=True, reason="fired", trigger_ctx={"changed_summary": "changed"}
    )

    ctx = {"redis": AsyncMock()}
    ctx["redis"].set = AsyncMock(return_value=True)  # lock acquired
    ctx["redis"].delete = AsyncMock()
    ctx["job_try"] = 1

    with (
        patch("app.worker.AsyncSessionLocal") as mock_session_cls,
        patch("app.worker.evaluate_trigger", new=AsyncMock(return_value=fired_result)),
        patch(
            "app.worker.run_agent_for_user", new=AsyncMock(return_value="done")
        ) as mock_agent,
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = AsyncMock(return_value=mock_job)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session_cls.return_value = mock_session

        from app.worker import execute_cron_job

        await execute_cron_job(ctx, job_id=job_id, run_group_id=run_group_id)

    mock_agent.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_cron_job_lock_contention_returns_early():
    """If lock cannot be acquired, execution is skipped silently."""
    ctx = {"redis": AsyncMock()}
    ctx["redis"].set = AsyncMock(return_value=None)  # lock NOT acquired
    ctx["job_try"] = 1

    with patch("app.worker.AsyncSessionLocal"):
        from app.worker import execute_cron_job

        # Should return without raising
        await execute_cron_job(
            ctx, job_id=str(uuid.uuid4()), run_group_id=str(uuid.uuid4())
        )
