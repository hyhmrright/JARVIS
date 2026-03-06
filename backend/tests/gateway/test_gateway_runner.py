"""Tests for agent_runner.run_agent_for_user."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.gateway.agent_runner import run_agent_for_user


@pytest.mark.asyncio
async def test_run_agent_for_user_returns_ai_reply():
    """Successful run returns the AI message content."""
    mock_us = MagicMock()
    mock_us.model_provider = "deepseek"
    mock_us.model_name = "deepseek-chat"
    mock_us.api_keys = {}
    mock_us.persona_override = None
    mock_us.enabled_tools = None

    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=mock_us)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {"messages": [AIMessage(content="任务完成。")]}

    with (
        patch("app.gateway.agent_runner.AsyncSessionLocal", return_value=mock_ctx),
        patch("app.gateway.agent_runner.resolve_api_keys", return_value=["fake-key"]),
        patch("app.gateway.agent_runner.create_graph", return_value=mock_graph),
    ):
        result = await run_agent_for_user(
            "00000000-0000-0000-0000-000000000001", "帮我做个计划"
        )

    assert result == "任务完成。"
    mock_graph.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_run_agent_for_user_no_api_key_returns_message():
    """Missing API key returns a descriptive error string without raising."""
    mock_us = MagicMock()
    mock_us.model_provider = "deepseek"
    mock_us.model_name = "deepseek-chat"
    mock_us.api_keys = {}
    mock_us.persona_override = None
    mock_us.enabled_tools = None

    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=mock_us)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.gateway.agent_runner.AsyncSessionLocal", return_value=mock_ctx),
        patch("app.gateway.agent_runner.resolve_api_keys", return_value=[]),
    ):
        result = await run_agent_for_user(
            "00000000-0000-0000-0000-000000000001", "test"
        )

    assert result == "No API key configured for this user."


@pytest.mark.asyncio
async def test_run_agent_for_user_exception_returns_chinese_message():
    """Any unhandled exception returns a user-friendly Chinese error string."""
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("app.gateway.agent_runner.AsyncSessionLocal", return_value=mock_ctx):
        result = await run_agent_for_user(
            "00000000-0000-0000-0000-000000000001", "test"
        )

    assert result == "抱歉，处理请求时出现错误，请稍后重试。"
