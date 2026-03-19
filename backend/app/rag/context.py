"""Shared RAG context helper for use in any agent execution path."""

import time

import structlog

from app.core.metrics import rag_retrieval_duration_seconds
from app.rag import retriever as _retriever

logger = structlog.get_logger(__name__)


async def build_rag_context(
    user_id: str,
    query: str,
    openai_key: str | None,
    workspace_ids: list[str] | None = None,
) -> str:
    """Retrieve relevant chunks and return them as a formatted context string.

    When workspace_ids is provided, also searches workspace collections.
    Returns empty string when no key is provided, no chunks are found,
    or retrieval fails. Never raises.
    """
    if not openai_key:
        return ""
    _t0 = time.monotonic()
    try:
        if workspace_ids:
            chunks = await _retriever.retrieve_context_multi(
                query, user_id, workspace_ids, openai_key
            )
        else:
            chunks = await _retriever.retrieve_context(query, user_id, openai_key)
        if not chunks:
            return ""
        logger.info(
            "rag_context_built",
            user_id=user_id,
            chunk_count=len(chunks),
            workspace_ids=workspace_ids,
        )
        return _retriever.format_rag_context(chunks)
    except Exception:
        logger.warning("rag_context_build_failed", exc_info=True)
        return ""
    finally:
        rag_retrieval_duration_seconds.observe(time.monotonic() - _t0)
