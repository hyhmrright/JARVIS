"""Tests for expert agent factories."""

from app.agent.experts.code_agent import create_code_agent_graph
from app.agent.experts.research_agent import create_research_agent_graph
from app.agent.experts.writing_agent import create_writing_agent_graph


def test_code_agent_returns_compiled_graph():
    """create_code_agent_graph returns a compiled LangGraph."""
    graph = create_code_agent_graph(
        provider="deepseek",
        model="deepseek-chat",
        api_key="test",
        user_id="user123",
    )
    assert graph is not None
    assert hasattr(graph, "astream")


def test_research_agent_returns_compiled_graph():
    """create_research_agent_graph returns a compiled LangGraph."""
    graph = create_research_agent_graph(
        provider="deepseek",
        model="deepseek-chat",
        api_key="test",
        user_id="user123",
        openai_api_key="oai_test",
    )
    assert graph is not None
    assert hasattr(graph, "astream")


def test_writing_agent_returns_compiled_graph():
    """create_writing_agent_graph returns a compiled LangGraph."""
    graph = create_writing_agent_graph(
        provider="deepseek",
        model="deepseek-chat",
        api_key="test",
        user_id="user123",
    )
    assert graph is not None
    assert hasattr(graph, "astream")
