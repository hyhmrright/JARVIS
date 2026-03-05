"""Unit tests for multi-agent routing dispatch in chat.py."""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from app.api.chat import _build_expert_graph, _format_sse

_COMMON_KWARGS: dict = dict(
    provider="openai",
    model="gpt-4o",
    api_key="sk-test",
    api_keys=None,
    user_id="user-1",
    openai_api_key="sk-oai",
    tavily_api_key=None,
    enabled_tools=None,
    mcp_tools=[],
    plugin_tools=None,
    conversation_id="conv-1",
)


def test_routing_sse_event_format() -> None:
    """routing SSE event must include type and agent fields."""
    event = _format_sse({"type": "routing", "agent": "code"})
    assert '"type": "routing"' in event
    assert '"agent": "code"' in event
    assert event.startswith("data: ")
    assert event.endswith("\n\n")


@patch("app.agent.experts.create_code_agent_graph")
@patch("app.agent.graph.create_graph")
def test_build_expert_graph_code_route(
    mock_create_graph: MagicMock, mock_code: MagicMock
) -> None:
    """'code' route should call create_code_agent_graph, not create_graph."""
    mock_code.return_value = MagicMock()
    _build_expert_graph("code", **_COMMON_KWARGS)
    mock_code.assert_called_once()
    mock_create_graph.assert_not_called()


@patch("app.agent.experts.create_research_agent_graph")
@patch("app.agent.graph.create_graph")
def test_build_expert_graph_research_route(
    mock_create_graph: MagicMock, mock_research: MagicMock
) -> None:
    """'research' route should call create_research_agent_graph."""
    mock_research.return_value = MagicMock()
    _build_expert_graph("research", **_COMMON_KWARGS)
    mock_research.assert_called_once()
    mock_create_graph.assert_not_called()


@patch("app.agent.experts.create_writing_agent_graph")
@patch("app.agent.graph.create_graph")
def test_build_expert_graph_writing_route(
    mock_create_graph: MagicMock, mock_writing: MagicMock
) -> None:
    """'writing' route should call create_writing_agent_graph."""
    mock_writing.return_value = MagicMock()
    _build_expert_graph("writing", **_COMMON_KWARGS)
    mock_writing.assert_called_once()
    mock_create_graph.assert_not_called()


@patch("app.api.chat.create_graph")
def test_build_expert_graph_simple_route(mock_create_graph: MagicMock) -> None:
    """'simple' route should fall through to create_graph."""
    mock_create_graph.return_value = MagicMock()
    _build_expert_graph("simple", **_COMMON_KWARGS)
    mock_create_graph.assert_called_once()


@patch("app.api.chat.create_graph")
def test_build_expert_graph_unknown_route_falls_back(
    mock_create_graph: MagicMock,
) -> None:
    """Unknown route labels should fall back to the standard ReAct graph."""
    mock_create_graph.return_value = MagicMock()
    _build_expert_graph("unknown_label", **_COMMON_KWARGS)
    mock_create_graph.assert_called_once()


@pytest.mark.parametrize("route", ["code", "research", "writing", "simple"])
def test_build_expert_graph_returns_graph_object(route: str) -> None:
    """_build_expert_graph should always return a non-None value for valid routes."""
    fake_graph = MagicMock()
    with ExitStack() as stack:
        for target in [
            "app.agent.experts.create_code_agent_graph",
            "app.agent.experts.create_research_agent_graph",
            "app.agent.experts.create_writing_agent_graph",
            "app.api.chat.create_graph",
        ]:
            stack.enter_context(patch(target, return_value=fake_graph))
        result = _build_expert_graph(route, **_COMMON_KWARGS)
    assert result is not None
