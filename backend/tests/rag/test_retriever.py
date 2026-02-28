from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.retriever import RetrievedChunk, format_rag_context, retrieve_context


def _make_hit(
    score: float, text: str, doc_name: str | None = "test_doc.pdf"
) -> MagicMock:
    """Build a fake Qdrant ScoredPoint."""
    hit = MagicMock()
    hit.score = score
    hit.payload = {"text": text}
    if doc_name is not None:
        hit.payload["doc_name"] = doc_name
    return hit


@pytest.fixture
def mock_embedder():
    embedder = MagicMock()
    embedder.aembed_query = AsyncMock(return_value=[0.1] * 1536)
    return embedder


@pytest.mark.asyncio
async def test_retrieve_context_returns_chunks_above_threshold(mock_embedder):
    """Hits above score_threshold are returned; hits below are filtered out."""
    hits = [
        _make_hit(score=0.85, text="Relevant content"),
        _make_hit(score=0.60, text="Less relevant content"),
    ]
    mock_client = AsyncMock()
    mock_client.search = AsyncMock(return_value=hits)

    with (
        patch("app.rag.retriever.get_qdrant_client", return_value=mock_client),
        patch("app.rag.retriever.get_embedder", return_value=mock_embedder),
    ):
        result = await retrieve_context(
            query="test query",
            user_id="user-123",
            openai_api_key="sk-test",
            score_threshold=0.7,
        )

    assert len(result) == 1
    assert isinstance(result[0], RetrievedChunk)
    assert result[0].content == "Relevant content"
    assert result[0].score == 0.85
    assert result[0].document_name == "test_doc.pdf"


@pytest.mark.asyncio
async def test_retrieve_context_returns_empty_on_404(mock_embedder):
    """A 404 UnexpectedResponse from Qdrant (no collection) returns empty list."""
    from qdrant_client.http.exceptions import UnexpectedResponse

    mock_client = AsyncMock()
    mock_client.search = AsyncMock(
        side_effect=UnexpectedResponse(
            status_code=404,
            reason_phrase="Not Found",
            content=b"collection not found",
            headers={},
        )
    )

    with (
        patch("app.rag.retriever.get_qdrant_client", return_value=mock_client),
        patch("app.rag.retriever.get_embedder", return_value=mock_embedder),
    ):
        result = await retrieve_context(
            query="test query",
            user_id="user-404",
            openai_api_key="sk-test",
        )

    assert result == []


@pytest.mark.asyncio
async def test_retrieve_context_returns_empty_on_general_error(mock_embedder):
    """Any unexpected exception from Qdrant returns empty list (never raises)."""
    mock_client = AsyncMock()
    mock_client.search = AsyncMock(side_effect=RuntimeError("connection refused"))

    with (
        patch("app.rag.retriever.get_qdrant_client", return_value=mock_client),
        patch("app.rag.retriever.get_embedder", return_value=mock_embedder),
    ):
        result = await retrieve_context(
            query="test query",
            user_id="user-err",
            openai_api_key="sk-test",
        )

    assert result == []


@pytest.mark.asyncio
async def test_retrieve_context_falls_back_doc_name_when_missing(mock_embedder):
    """When doc_name is absent from payload, fall back to 'Unknown document'."""
    hits = [_make_hit(score=0.90, text="Some content", doc_name=None)]
    mock_client = AsyncMock()
    mock_client.search = AsyncMock(return_value=hits)

    with (
        patch("app.rag.retriever.get_qdrant_client", return_value=mock_client),
        patch("app.rag.retriever.get_embedder", return_value=mock_embedder),
    ):
        result = await retrieve_context(
            query="test query",
            user_id="user-123",
            openai_api_key="sk-test",
        )

    assert len(result) == 1
    assert result[0].document_name == "Unknown document"


def test_format_rag_context_with_chunks():
    """format_rag_context renders header, doc name, score, content, and footer."""
    chunks = [
        RetrievedChunk(
            document_name="report.pdf", content="Revenue grew 20%.", score=0.92
        ),
        RetrievedChunk(document_name="notes.txt", content="Q3 summary.", score=0.81),
    ]
    result = format_rag_context(chunks)

    assert result.startswith("[Knowledge Base Context]")
    assert "report.pdf" in result
    assert "0.92" in result
    assert "Revenue grew 20%." in result
    assert "notes.txt" in result
    assert "0.81" in result
    assert "Q3 summary." in result
    assert "Cite document names" in result


def test_format_rag_context_empty_list():
    """format_rag_context returns empty string for an empty chunk list."""
    result = format_rag_context([])
    assert result == ""
