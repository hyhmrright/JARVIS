"""Shared RAG context helper for use in any agent execution path."""

import time

import structlog

from app.core.metrics import rag_retrieval_duration_seconds
from app.rag import retriever as _retriever
from app.rag.retriever import RetrievedChunk

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
        return _format_chunks(chunks)
    except Exception:
        logger.warning("rag_context_build_failed", exc_info=True)
        return ""
    finally:
        rag_retrieval_duration_seconds.observe(time.monotonic() - _t0)


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    lines = ["[Knowledge Base Context]", ""]
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"[{i}] {chunk.document_name} (relevance: {chunk.score:.2f})")
        lines.append(chunk.content)
        lines.append("")
    source_list = ", ".join(
        f'[{i}] "{c.document_name}"' for i, c in enumerate(chunks, 1)
    )
    lines.append(
        "When using information from the context above, cite it inline using the "
        f"reference numbers (e.g. [1], [2]). Available sources: {source_list}."
    )
    return "\n".join(lines)
