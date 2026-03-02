from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool

from app.agent.graph import _resolve_tools, create_graph


async def test_graph_returns_ai_message():
    mock_response = AIMessage(content="Hello!")
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    with patch("app.agent.graph.get_llm", return_value=mock_llm):
        graph = create_graph(provider="deepseek", model="deepseek-chat", api_key="test")
        result = await graph.ainvoke({"messages": [HumanMessage(content="Hi")]})
    assert result["messages"][-1].content == "Hello!"


def _make_tool(name: str) -> BaseTool:
    t = MagicMock(spec=BaseTool)
    t.name = name
    return t


def test_plugin_tools_included_when_enabled_tools_is_none():
    plugin_tool = _make_tool("my_plugin_action")
    tools = _resolve_tools(
        None,
        user_id=None,
        openai_api_key=None,
        tavily_api_key=None,
        plugin_tools=[plugin_tool],
    )
    assert plugin_tool in tools


def test_plugin_tools_included_when_plugin_in_enabled_tools():
    plugin_tool = _make_tool("my_plugin_action")
    tools = _resolve_tools(
        ["plugin"],
        user_id=None,
        openai_api_key=None,
        tavily_api_key=None,
        plugin_tools=[plugin_tool],
    )
    assert plugin_tool in tools


def test_plugin_tools_excluded_when_plugin_not_in_enabled_tools():
    plugin_tool = _make_tool("my_plugin_action")
    tools = _resolve_tools(
        ["datetime"],
        user_id=None,
        openai_api_key=None,
        tavily_api_key=None,
        plugin_tools=[plugin_tool],
    )
    assert plugin_tool not in tools


def test_mcp_tools_included_when_enabled_tools_is_none():
    mcp_tool = _make_tool("mcp_action")
    tools = _resolve_tools(
        None,
        user_id=None,
        openai_api_key=None,
        tavily_api_key=None,
        mcp_tools=[mcp_tool],
    )
    assert mcp_tool in tools


def test_mcp_tools_included_when_mcp_in_enabled_tools():
    mcp_tool = _make_tool("mcp_action")
    tools = _resolve_tools(
        ["mcp"],
        user_id=None,
        openai_api_key=None,
        tavily_api_key=None,
        mcp_tools=[mcp_tool],
    )
    assert mcp_tool in tools


def test_mcp_tools_excluded_when_mcp_not_in_enabled_tools():
    mcp_tool = _make_tool("mcp_action")
    tools = _resolve_tools(
        ["datetime"],
        user_id=None,
        openai_api_key=None,
        tavily_api_key=None,
        mcp_tools=[mcp_tool],
    )
    assert mcp_tool not in tools
