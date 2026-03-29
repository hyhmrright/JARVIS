# backend/tests/services/test_agent_execution.py
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.llm_config import AgentConfig, ResolvedLLMConfig
from app.services.agent_execution import AgentExecutionService


def _make_config(user_id=None):
    llm = ResolvedLLMConfig(
        provider="deepseek",
        model_name="deepseek-chat",
        api_key="sk-test",
        api_keys=["sk-test"],
        enabled_tools=[],
        persona_override=None,
        raw_keys={},
    )
    return AgentConfig(llm=llm, user_id=user_id or str(uuid.uuid4()))


@pytest.mark.anyio
async def test_run_blocking_returns_ai_reply():
    """run_blocking() must return the last AI message content as a string."""
    from langchain_core.messages import AIMessage, HumanMessage

    config = _make_config()
    messages = [HumanMessage(content="hello")]

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"messages": [AIMessage(content="Hi there!")]}
    )

    with patch(
        "app.services.agent_execution.create_graph",
        return_value=mock_graph,
    ):
        svc = AgentExecutionService()
        result = await svc.run_blocking(messages, config)

    assert result == "Hi there!"


@pytest.mark.anyio
async def test_run_blocking_raises_on_empty_messages():
    """run_blocking() must raise ValueError when graph returns no messages."""
    from langchain_core.messages import HumanMessage

    config = _make_config()
    messages = [HumanMessage(content="hello")]

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value={"messages": []})

    with patch("app.services.agent_execution.create_graph", return_value=mock_graph):
        svc = AgentExecutionService()
        with pytest.raises(ValueError, match="no messages"):
            await svc.run_blocking(messages, config)
