from unittest.mock import AsyncMock, patch

import pytest

from app.tools.rag_tool import create_rag_search_tool


@pytest.fixture()
def rag_tool():
    return create_rag_search_tool(user_id="test-user-123", openai_api_key="sk-test-key")


async def test_rag_search_returns_formatted_results(rag_tool):
    mock_results = ["chunk about Python basics", "chunk about Python decorators"]
    with patch(
        "app.tools.rag_tool.search_documents",
        new_callable=AsyncMock,
        return_value=mock_results,
    ) as mock_search:
        result = await rag_tool.ainvoke({"query": "Python"})
        mock_search.assert_awaited_once_with(
            "test-user-123", "Python", "sk-test-key", top_k=5
        )
    assert "chunk about Python basics" in result
    assert "chunk about Python decorators" in result


async def test_rag_search_no_results(rag_tool):
    with patch(
        "app.tools.rag_tool.search_documents",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await rag_tool.ainvoke({"query": "nonexistent topic"})
    assert "no relevant" in result.lower()


async def test_rag_search_handles_error(rag_tool):
    with patch(
        "app.tools.rag_tool.search_documents",
        new_callable=AsyncMock,
        side_effect=Exception("Qdrant connection failed"),
    ):
        result = await rag_tool.ainvoke({"query": "test"})
    assert "error" in result.lower()


async def test_rag_tool_has_correct_name(rag_tool):
    assert rag_tool.name == "rag_search"


async def test_rag_tool_closes_over_user_context():
    """Different user_id/key combos produce independent tools."""
    tool_a = create_rag_search_tool("user-a", "key-a")
    tool_b = create_rag_search_tool("user-b", "key-b")
    with patch(
        "app.tools.rag_tool.search_documents",
        new_callable=AsyncMock,
        return_value=["result"],
    ) as mock_search:
        await tool_a.ainvoke({"query": "q"})
        mock_search.assert_awaited_with("user-a", "q", "key-a", top_k=5)
        await tool_b.ainvoke({"query": "q"})
        mock_search.assert_awaited_with("user-b", "q", "key-b", top_k=5)
