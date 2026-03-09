import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scheduler.runner import _execute_cron_job


@pytest.mark.asyncio
async def test_execute_cron_job_flow():
    """验证 Cron 任务触发时，能够从数据库加载并运行 Agent。"""
    job_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    task = "summarize news"

    with (
        patch("app.db.session.AsyncSessionLocal") as mock_session_factory,
        patch("app.gateway.agent_runner.run_agent_for_user") as mock_run_agent,
        patch("app.scheduler.triggers.evaluate_trigger", return_value=True),
    ):
        mock_db = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_db

        mock_job = MagicMock()
        mock_job.is_active = True
        mock_job.trigger_type = "cron"
        mock_job.trigger_metadata = {}
        mock_db.get.return_value = mock_job

        await _execute_cron_job(job_id, user_id, task)

        mock_db.get.assert_called_once()
        mock_run_agent.assert_called_once_with(user_id, task)
        mock_db.commit.assert_called_once()
