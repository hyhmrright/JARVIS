"""Tests for the RAG search tool using the enhanced retriever."""

from unittest.mock import AsyncMock, patch

import pytest

from app.rag.retriever import RetrievedChunk
from app.tools.rag_tool import create_rag_search_tool


@pytest.fixture()
def rag_tool():
    return create_rag_search_tool(user_id="test-user-123", openai_api_key="sk-test-key")


async def test_rag_tool_formats_results_with_document_names(rag_tool):
    """Verify the tool formats output with document names and relevance scores."""
    mock_chunks = [
        RetrievedChunk(
            document_name="report.pdf", content="Sales grew by 20% in Q3.", score=0.91
        ),
        RetrievedChunk(
            document_name="notes.txt",
            content="Meeting notes from January.",
            score=0.82,
        ),
    ]
    with patch(
        "app.tools.rag_tool.retrieve_context",
        new_callable=AsyncMock,
        return_value=mock_chunks,
    ):
        result = await rag_tool.ainvoke({"query": "quarterly sales"})

    assert "report.pdf" in result
    assert "0.91" in result
    assert "Sales grew by 20% in Q3." in result
    assert "notes.txt" in result
    assert "0.82" in result


async def test_rag_tool_returns_no_results_message_when_empty(rag_tool):
    """When the retriever returns an empty list the tool reports no results."""
    with patch(
        "app.tools.rag_tool.retrieve_context",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await rag_tool.ainvoke({"query": "nonexistent topic"})

    assert result.startswith("No relevant")


async def test_rag_tool_handles_retriever_exception(rag_tool):
    """When retrieve_context raises, the tool returns a graceful error message."""
    with patch(
        "app.tools.rag_tool.retrieve_context",
        new_callable=AsyncMock,
        side_effect=RuntimeError("embedding service unavailable"),
    ):
        result = await rag_tool.ainvoke({"query": "test query"})

    assert "Error" in result or "failed" in result
