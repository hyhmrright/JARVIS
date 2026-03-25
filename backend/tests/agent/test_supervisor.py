from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.supervisor import SupervisorState, create_supervisor_graph


@pytest.fixture()
def mock_llm():
    llm = AsyncMock()
    # First call: plan; second call: aggregate
    llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(content="1. Research topic A\n2. Research topic B"),
            AIMessage(content="Final combined answer from A and B"),
        ]
    )
    return llm


@pytest.fixture()
def mock_subagent():
    tool = AsyncMock()
    tool.ainvoke = AsyncMock(
        side_effect=[
            "Result for topic A",
            "Result for topic B",
        ]
    )
    return tool


@pytest.mark.asyncio
async def test_supervisor_plan_execute_aggregate(mock_llm, mock_subagent):
    with (
        patch("app.agent.supervisor.get_llm_with_fallback", return_value=mock_llm),
        patch(
            "app.agent.supervisor.create_subagent_tool",
            return_value=mock_subagent,
        ),
    ):
        graph = create_supervisor_graph(provider="test", model="m", api_key="k")
        result = await graph.ainvoke(
            SupervisorState(messages=[HumanMessage(content="Research both A and B")])
        )

    # Plan should have produced 2 steps
    assert len(result["plan"]) == 2
    # Both subtask results captured
    assert len(result["results"]) == 2
    assert "Result for topic A" in result["results"]
    # Final aggregated message
    assert any("Final combined answer" in str(m.content) for m in result["messages"])
    # LLM called twice: plan + aggregate
    assert mock_llm.ainvoke.call_count == 2
    # Subagent called once per subtask
    assert mock_subagent.ainvoke.call_count == 2


@pytest.mark.asyncio
async def test_supervisor_empty_plan():
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(content=""),  # Empty plan
            AIMessage(content="No subtasks needed, direct answer"),
        ]
    )
    mock_sub = AsyncMock()

    with (
        patch("app.agent.supervisor.get_llm_with_fallback", return_value=mock_llm),
        patch(
            "app.agent.supervisor.create_subagent_tool",
            return_value=mock_sub,
        ),
    ):
        graph = create_supervisor_graph(provider="test", model="m", api_key="k")
        result = await graph.ainvoke(
            SupervisorState(messages=[HumanMessage(content="Simple query")])
        )

    # No subtasks should have been executed
    assert mock_sub.ainvoke.call_count == 0
    assert len(result["plan"]) == 0
