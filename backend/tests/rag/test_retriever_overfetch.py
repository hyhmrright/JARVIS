"""Regression test: retriever overfetches candidates for reranking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.retriever import _RERANK_CANDIDATE_MULTIPLIER


def _make_mock_hits(n: int) -> list[MagicMock]:
    """Create n mock ScoredPoint objects."""
    hits = []
    for i in range(n):
        hit = MagicMock()
        hit.id = f"chunk_{i}"
        hit.payload = {"text": f"content {i}", "doc_name": f"doc_{i}"}
        hit.score = 1.0 - i * 0.1
        hits.append(hit)
    return hits


@pytest.mark.anyio
async def test_retriever_overfetches_for_reranking() -> None:
    """retrieve_context() fetches top_k * RERANK_CANDIDATE_MULTIPLIER candidates.

    The retriever intentionally overfetches so the reranker has a larger
    candidate pool to choose from, then returns at most top_k results.
    """
    from app.rag.retriever import retrieve_context

    top_k = 3
    expected_limit = top_k * _RERANK_CANDIDATE_MULTIPLIER
    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value=_make_mock_hits(expected_limit))
    mock_embedder = MagicMock()
    mock_embedder.aembed_query = AsyncMock(return_value=[0.1] * 1536)

    mock_get_client = AsyncMock(return_value=mock_client)
    with patch("app.rag.retriever.get_qdrant_client", mock_get_client):
        with patch("app.rag.retriever.get_embedder", return_value=mock_embedder):
            results = await retrieve_context(
                query="test query",
                user_id="test_user",
                openai_api_key="test-key",
                top_k=top_k,
            )

    actual_limit = mock_client.search.call_args.kwargs.get("limit", 0)
    assert actual_limit == expected_limit, (
        f"Expected search limit={expected_limit} "
        f"(top_k * {_RERANK_CANDIDATE_MULTIPLIER}), got {actual_limit}."
    )
    assert len(results) <= top_k
