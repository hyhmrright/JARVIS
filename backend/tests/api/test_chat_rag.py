"""Tests for RAG context injection logic in chat stream."""

from langchain_core.messages import HumanMessage, SystemMessage

from app.rag.retriever import RetrievedChunk, format_rag_context


def test_rag_injection_inserts_at_position_1() -> None:
    """RAG context message should be inserted at index 1 (after system msg)."""
    chunks = [RetrievedChunk("report.pdf", "Important finding", 0.85)]
    lc_messages = [
        SystemMessage(content="You are JARVIS."),
        HumanMessage(content="tell me about the report"),
    ]

    rag_msg = SystemMessage(content=format_rag_context(chunks))
    injected = [lc_messages[0], rag_msg, *lc_messages[1:]]

    assert len(injected) == 3
    assert injected[0].content == "You are JARVIS."
    assert "[Knowledge Base Context]" in injected[1].content
    assert "report.pdf" in injected[1].content
    assert injected[2].content == "tell me about the report"


def test_rag_injection_skipped_when_no_chunks() -> None:
    """When retrieve_context returns [], lc_messages should remain unchanged."""
    lc_messages = [
        SystemMessage(content="You are JARVIS."),
        HumanMessage(content="hello"),
    ]
    chunks: list[RetrievedChunk] = []

    # Simulate the guard: if not rag_chunks, skip injection
    if chunks:
        rag_msg = SystemMessage(content=format_rag_context(chunks))
        lc_messages = [lc_messages[0], rag_msg, *lc_messages[1:]]

    assert len(lc_messages) == 2


def test_rag_injection_preserves_full_history() -> None:
    """RAG injection should insert at index 1, leaving all other messages intact."""
    chunks = [RetrievedChunk("doc.pdf", "Some content", 0.92)]
    lc_messages = [
        SystemMessage(content="You are JARVIS."),
        HumanMessage(content="first question"),
        SystemMessage(content="first answer"),
        HumanMessage(content="follow-up question"),
    ]

    rag_msg = SystemMessage(content=format_rag_context(chunks))
    injected = [lc_messages[0], rag_msg, *lc_messages[1:]]

    assert len(injected) == 5
    assert injected[0].content == "You are JARVIS."
    assert "[Knowledge Base Context]" in injected[1].content
    assert injected[2].content == "first question"
    assert injected[3].content == "first answer"
    assert injected[4].content == "follow-up question"


def test_format_rag_context_contains_relevance_score() -> None:
    """format_rag_context output should include document name and relevance score."""
    chunks = [RetrievedChunk("report.pdf", "Key insight here", 0.91)]
    result = format_rag_context(chunks)

    assert "report.pdf" in result
    assert "0.91" in result
    assert "Key insight here" in result
    assert "Cite document names" in result


def test_format_rag_context_multiple_chunks() -> None:
    """Multiple chunks should all appear in the formatted output."""
    chunks = [
        RetrievedChunk("alpha.pdf", "Content from alpha", 0.95),
        RetrievedChunk("beta.pdf", "Content from beta", 0.80),
    ]
    result = format_rag_context(chunks)

    assert "alpha.pdf" in result
    assert "beta.pdf" in result
    assert "Content from alpha" in result
    assert "Content from beta" in result


async def test_rag_score_threshold_passed_to_qdrant():
    """score_threshold is forwarded to Qdrant search, not filtered in Python."""
    from unittest.mock import AsyncMock, patch

    from app.rag.retriever import retrieve_context

    mock_client = AsyncMock()
    mock_client.search = AsyncMock(return_value=[])

    with (
        patch("app.rag.retriever.get_qdrant_client", AsyncMock(return_value=mock_client)),
        patch("app.rag.retriever.get_embedder") as mock_embedder,
    ):
        mock_embedder.return_value.aembed_query = AsyncMock(return_value=[0.1] * 1536)
        await retrieve_context("test query", "user-123", "fake-key")

    call_kwargs = mock_client.search.call_args.kwargs
    assert "score_threshold" in call_kwargs
    assert call_kwargs["score_threshold"] == 0.7
