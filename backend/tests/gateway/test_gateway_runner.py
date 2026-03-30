"""Tests for agent_runner.run_agent_for_user."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateway.agent_runner import run_agent_for_user

_USER_ID = "00000000-0000-0000-0000-000000000001"


def _make_user_settings() -> MagicMock:
    """Return a MagicMock mimicking a UserSettings row with defaults."""
    us = MagicMock()
    us.model_provider = "deepseek"
    us.model_name = "deepseek-chat"
    us.api_keys = {}
    us.persona_override = None
    us.enabled_tools = None
    return us


@pytest.mark.asyncio
async def test_run_agent_for_user_returns_ai_reply():
    """Successful run returns the AI message content."""
    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=_make_user_settings())
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.gateway.agent_runner.AsyncSessionLocal", return_value=mock_ctx),
        patch("app.gateway.agent_runner.resolve_api_keys", return_value=["fake-key"]),
        patch("app.gateway.agent_runner.build_rag_context", AsyncMock(return_value="")),
        patch(
            "app.services.agent_execution.AgentExecutionService.run_blocking",
            AsyncMock(return_value="任务完成。"),
        ),
    ):
        result = await run_agent_for_user(_USER_ID, "帮我做个计划")

    assert result == "任务完成。"


@pytest.mark.asyncio
async def test_run_agent_for_user_no_api_key_returns_message():
    """Missing API key returns a descriptive error string without raising."""
    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=_make_user_settings())

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.gateway.agent_runner.AsyncSessionLocal", return_value=mock_ctx),
        patch("app.gateway.agent_runner.resolve_api_keys", return_value=[]),
    ):
        result = await run_agent_for_user(_USER_ID, "test")

    assert result == "未配置可用的 API Key，请先在设置页面中添加。"


@pytest.mark.asyncio
async def test_run_agent_for_user_exception_propagates():
    """Unhandled exceptions are re-raised so callers can detect failures reliably."""
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("app.gateway.agent_runner.AsyncSessionLocal", return_value=mock_ctx):
        with pytest.raises(RuntimeError, match="DB down"):
            await run_agent_for_user(_USER_ID, "test")
