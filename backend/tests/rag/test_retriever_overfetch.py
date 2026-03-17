"""Regression test: retriever must not overfetch from Qdrant."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
async def test_retriever_uses_top_k_not_double() -> None:
    """retrieve_context() must pass limit=top_k to Qdrant, not limit=top_k*2.

    FAILS before fix: retriever calls client.search(limit=top_k * 2).
    PASSES after fix: limit parameter equals top_k.
    """
    from app.rag.retriever import retrieve_context

    top_k = 3
    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value=_make_mock_hits(top_k))
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

    # The Qdrant search must have been called with limit=top_k, not top_k*2
    actual_limit = mock_client.search.call_args.kwargs.get("limit", 0)
    assert actual_limit == top_k, (
        f"Expected search limit={top_k}, got {actual_limit}. "
        "Retriever is overfetching with top_k * 2."
    )
    assert len(results) <= top_k
