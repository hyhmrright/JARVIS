from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.retriever import (
    RetrievedChunk,
    _keyword_score,
    _rerank,
    format_rag_context,
    retrieve_context,
)


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
    """score_threshold is forwarded to Qdrant; Qdrant returns only matching hits."""
    hits = [_make_hit(score=0.85, text="Relevant content")]
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

    call_kwargs = mock_client.search.call_args.kwargs
    assert call_kwargs.get("score_threshold") == 0.7
    # Single-collection path fetches top_k * 3 candidates for reranking.
    assert call_kwargs.get("limit") == 5 * 3  # default top_k=5, multiplier=3

    assert len(result) == 1
    assert isinstance(result[0], RetrievedChunk)
    assert result[0].content == "Relevant content"
    # score is now the combined vector+keyword score (query "test query" has no
    # overlap with "Relevant content", so keyword_score=0, combined=0.7*0.85).
    assert result[0].score == pytest.approx(0.7 * 0.85)
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


# ---------------------------------------------------------------------------
# _keyword_score unit tests
# ---------------------------------------------------------------------------


def test_keyword_score_full_overlap():
    """All query words present in text → score 1.0."""
    assert _keyword_score("machine learning", "machine learning is powerful") == 1.0


def test_keyword_score_no_overlap():
    """No shared words → score 0.0."""
    assert _keyword_score("machine learning", "cats and dogs") == 0.0


def test_keyword_score_partial_overlap():
    """Half of query words present → score 0.5."""
    score = _keyword_score("machine learning", "I love machine tools")
    assert score == pytest.approx(0.5)


def test_keyword_score_empty_query():
    """Empty query → score 0.0 (no division by zero)."""
    assert _keyword_score("", "some text here") == 0.0


def test_keyword_score_empty_text():
    """Non-empty query but empty text → score 0.0."""
    assert _keyword_score("machine learning", "") == 0.0


def test_keyword_score_both_empty():
    """Both empty → score 0.0."""
    assert _keyword_score("", "") == 0.0


def test_keyword_score_punctuation_stripped():
    """Punctuation in query/text is ignored during tokenisation."""
    # "machine," should match "machine" in text
    assert _keyword_score("machine, learning!", "machine learning is great") == 1.0


def test_keyword_score_case_insensitive():
    """Matching is case-insensitive."""
    assert _keyword_score("Machine Learning", "machine learning rocks") == 1.0


def test_keyword_score_clamped_at_one():
    """Score never exceeds 1.0 even if text has more words than query."""
    score = _keyword_score("ai", "ai ai ai systems")
    assert score <= 1.0


# ---------------------------------------------------------------------------
# _rerank unit tests
# ---------------------------------------------------------------------------


def test_rerank_returns_top_k():
    """_rerank limits output to top_k results."""
    chunks = [
        RetrievedChunk(document_name="a", content="hello world", score=0.8),
        RetrievedChunk(document_name="b", content="foo bar baz", score=0.9),
        RetrievedChunk(document_name="c", content="hello there", score=0.75),
    ]
    result = _rerank(chunks, "hello", top_k=2)
    assert len(result) == 2


def test_rerank_prefers_keyword_match():
    """A chunk with lower vector score but high keyword overlap should rank higher."""
    # chunk_a: high vector score, no keyword match
    chunk_a = RetrievedChunk(
        document_name="a", content="unrelated content xyz", score=0.95
    )
    # chunk_b: lower vector score, full keyword match
    chunk_b = RetrievedChunk(
        document_name="b", content="machine learning tutorial", score=0.80
    )

    result = _rerank([chunk_a, chunk_b], "machine learning", top_k=2)
    assert result[0].document_name == "b"


def test_rerank_updates_score_to_combined():
    """_rerank updates chunk.score to the combined vector+keyword score."""
    chunk = RetrievedChunk(document_name="a", content="machine learning", score=0.88)
    result = _rerank([chunk], "machine learning", top_k=1)
    # query "machine learning" fully overlaps with content → keyword_score=1.0
    expected = 0.7 * 0.88 + 0.3 * 1.0
    assert result[0].score == pytest.approx(expected)


def test_rerank_empty_input():
    """_rerank handles an empty candidates list gracefully."""
    assert _rerank([], "query", top_k=5) == []


# ---------------------------------------------------------------------------
# format_rag_context tests
# ---------------------------------------------------------------------------


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


@pytest.mark.asyncio
async def test_index_document_stores_doc_name_in_payload() -> None:
    """index_document should store doc_name in each Qdrant point payload."""
    from app.rag.indexer import index_document

    captured_points: list = []

    async def fake_upsert(collection_name: str, points: list) -> None:
        captured_points.extend(points)

    mock_client = AsyncMock()
    mock_client.upsert = fake_upsert

    with (
        patch("app.rag.indexer.get_qdrant_client", return_value=mock_client),
        patch("app.rag.indexer.ensure_collection", new_callable=AsyncMock),
        patch("app.rag.indexer.get_embedder") as mock_ef,
    ):
        mock_emb = AsyncMock()
        mock_emb.aembed_documents.return_value = [[0.1] * 1536]
        mock_ef.return_value = mock_emb

        await index_document(
            user_id="u1",
            doc_id="d1",
            text="hello world",
            api_key="key",
            doc_name="report.pdf",
        )

    assert len(captured_points) > 0
    assert all(p.payload.get("doc_name") == "report.pdf" for p in captured_points)
