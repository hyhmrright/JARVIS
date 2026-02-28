from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.tools.subagent_tool import MAX_DEPTH, create_subagent_tool


@pytest.mark.asyncio
async def test_subagent_returns_result():
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {"messages": [AIMessage(content="Sub-result")]}

    with patch("app.agent.graph.create_graph", return_value=mock_graph):
        tool = create_subagent_tool(
            provider="test",
            model="m",
            api_key="k",
            current_depth=0,
        )
        result = await tool.ainvoke({"task": "Do something"})

    assert result == "Sub-result"
    mock_graph.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_subagent_depth_limit():
    tool = create_subagent_tool(
        provider="test",
        model="m",
        api_key="k",
        current_depth=MAX_DEPTH,
    )
    result = await tool.ainvoke({"task": "Do something"})
    assert "maximum depth" in result


@pytest.mark.asyncio
async def test_subagent_strips_subagent_from_child_tools():
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {"messages": [AIMessage(content="done")]}

    with patch("app.agent.graph.create_graph", return_value=mock_graph) as mock_create:
        tool = create_subagent_tool(
            provider="test",
            model="m",
            api_key="k",
            current_depth=0,
            enabled_tools=["datetime", "subagent", "shell"],
        )
        await tool.ainvoke({"task": "test"})

    # subagent should be stripped from child tools
    _, call_kwargs = mock_create.call_args
    child_tools = call_kwargs.get("enabled_tools", [])
    assert "subagent" not in child_tools
