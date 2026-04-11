from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from app.tools.subagent_tool import MAX_DEPTH, create_subagent_tool, set_graph_factory


class MockGraphFactory:
    def __init__(self, mock_graph):
        self.mock_graph = mock_graph
        self.call_kwargs = {}

    async def create(self, messages, config):
        self.call_kwargs = config
        return self.mock_graph


@pytest.mark.asyncio
async def test_subagent_returns_result():
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {"messages": [AIMessage(content="Sub-result")]}
    factory = MockGraphFactory(mock_graph)
    set_graph_factory(factory)

    try:
        tool = create_subagent_tool(
            provider="test",
            model="m",
            api_key="k",
            current_depth=0,
        )
        result = await tool.ainvoke({"task": "Do something"})

        assert result == "Sub-result"
        mock_graph.ainvoke.assert_called_once()
    finally:
        set_graph_factory(None)


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
    factory = MockGraphFactory(mock_graph)
    set_graph_factory(factory)

    try:
        tool = create_subagent_tool(
            provider="test",
            model="m",
            api_key="k",
            current_depth=0,
            enabled_tools=["datetime", "subagent", "shell"],
        )
        await tool.ainvoke({"task": "test"})

        # subagent should be stripped from child tools
        child_tools = factory.call_kwargs.get("enabled_tools", [])
        assert "subagent" not in child_tools
    finally:
        set_graph_factory(None)
