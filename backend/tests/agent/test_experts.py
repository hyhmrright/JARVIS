"""Tests for expert agent factories."""

from unittest.mock import patch

import pytest

from app.agent.experts.code_agent import create_code_agent_graph
from app.agent.experts.research_agent import create_research_agent_graph
from app.agent.experts.writing_agent import create_writing_agent_graph

_CASES = [
    pytest.param(
        "app.agent.experts.code_agent.create_graph",
        create_code_agent_graph,
        {},
        ["code_exec", "shell", "file", "datetime"],
        id="code_agent",
    ),
    pytest.param(
        "app.agent.experts.research_agent.create_graph",
        create_research_agent_graph,
        {"openai_api_key": "oai_test"},
        ["rag_search", "search", "web_fetch", "datetime"],
        id="research_agent",
    ),
    pytest.param(
        "app.agent.experts.writing_agent.create_graph",
        create_writing_agent_graph,
        {},
        ["rag_search", "web_fetch", "datetime"],
        id="writing_agent",
    ),
]


@pytest.mark.parametrize("patch_target,factory_fn,extra_kwargs,expected_tools", _CASES)
def test_expert_agent_passes_correct_tools_to_create_graph(
    patch_target, factory_fn, extra_kwargs, expected_tools
):
    """Each expert factory delegates to create_graph with its specific tool set."""
    with patch(patch_target) as mock_create:
        factory_fn(
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
            user_id="user123",
            **extra_kwargs,
        )
    mock_create.assert_called_once()
    # Use .get() to guard against KeyError if enabled_tools is ever passed positionally.
    assert mock_create.call_args.kwargs.get("enabled_tools") == expected_tools
