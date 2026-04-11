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
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.gateway.agent_runner.AsyncSessionLocal", return_value=mock_ctx),
        patch(
            "app.services.agent_engine.AgentEngine.run_blocking",
            AsyncMock(return_value="任务完成。"),
        ),
    ):
        result = await run_agent_for_user(_USER_ID, "帮我做个计划")

    assert result == "任务完成。"


@pytest.mark.asyncio
async def test_run_agent_for_user_exception_propagates():
    """Unhandled exceptions are re-raised so callers can detect failures reliably."""
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("app.gateway.agent_runner.AsyncSessionLocal", return_value=mock_ctx):
        with pytest.raises(RuntimeError, match="DB down"):
            await run_agent_for_user(_USER_ID, "test")
