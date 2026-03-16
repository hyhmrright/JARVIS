import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import CronJob
from app.tools.cron_tool import create_cron_tools


@pytest.mark.asyncio
async def test_cron_set_semantic_watcher_e2e():
    """验证通过 cron_set 设置语义监控任务。"""
    user_id = str(uuid.uuid4())
    cron_set, cron_list, _ = create_cron_tools(user_id)

    schedule = "0 9 * * *"
    task = "监控 AI 新闻"
    trigger_type = "semantic_watcher"
    metadata = {"url": "https://example.com/ai", "target": "主旨"}

    with (
        patch("app.tools.cron_tool.AsyncSessionLocal") as mock_session_factory,
        patch("app.scheduler.runner.register_cron_job") as mock_register,
    ):
        mock_db = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_db

        # 模拟 commit 和 refresh
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await cron_set.ainvoke(
            {
                "schedule": schedule,
                "task": task,
                "trigger_type": trigger_type,
                "metadata": metadata,
            }
        )

        assert "Scheduled" in result
        assert "type: semantic_watcher" in result

        # 验证数据库调用
        args, kwargs = mock_db.add.call_args
        job = args[0]
        assert isinstance(job, CronJob)
        assert job.trigger_type == "semantic_watcher"
        assert job.trigger_metadata == metadata
        assert job.task == task

        # 验证调度器注册
        mock_register.assert_called_once()


@pytest.mark.asyncio
async def test_cron_list_with_semantic_info():
    """验证 cron_list 能显示语义监控信息。"""
    user_id = str(uuid.uuid4())
    _, cron_list, _ = create_cron_tools(user_id)

    # 模拟数据库返回一个语义监控任务
    mock_job = MagicMock(spec=CronJob)
    mock_job.id = uuid.uuid4()
    mock_job.user_id = uuid.UUID(user_id)
    mock_job.task = "监控价格"
    mock_job.schedule = "0 0 * * *"
    mock_job.trigger_type = "semantic_watcher"
    mock_job.trigger_metadata = {"url": "http://shop.com", "target": "价格"}
    mock_job.last_run_at = None
    mock_job.is_active = True

    with patch("app.tools.cron_tool.AsyncSessionLocal") as mock_session_factory:
        mock_db = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_db

        mock_results = MagicMock()
        mock_results.all.return_value = [mock_job]
        mock_db.scalars.return_value = mock_results

        result = await cron_list.ainvoke({})

        assert "监控价格" in result
        assert "type: semantic_watcher" in result
        assert "meta: {'url': 'http://shop.com', 'target': '价格'}" in result
