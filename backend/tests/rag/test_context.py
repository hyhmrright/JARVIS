from unittest.mock import AsyncMock, patch

import pytest

from app.rag.context import build_rag_context


@pytest.mark.asyncio
async def test_build_rag_context_returns_empty_without_key():
    result = await build_rag_context(user_id="u1", query="test", openai_key=None)
    assert result == ""


@pytest.mark.asyncio
async def test_build_rag_context_returns_empty_when_no_chunks():
    with patch(
        "app.rag.retriever.retrieve_context",
        new=AsyncMock(return_value=[]),
    ):
        result = await build_rag_context(
            user_id="u1", query="test", openai_key="sk-test"
        )
    assert result == ""


@pytest.mark.asyncio
async def test_build_rag_context_formats_chunks():
    from app.rag.retriever import RetrievedChunk

    chunk = RetrievedChunk(document_name="guide.pdf", content="Hello world", score=0.9)
    with patch(
        "app.rag.retriever.retrieve_context",
        new=AsyncMock(return_value=[chunk]),
    ):
        result = await build_rag_context(
            user_id="u1", query="test", openai_key="sk-test"
        )
    assert "guide.pdf" in result
    assert "Hello world" in result
