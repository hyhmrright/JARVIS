"""Shared RAG context helper for use in any agent execution path."""

import structlog

from app.rag import retriever as _retriever
from app.rag.retriever import RetrievedChunk

logger = structlog.get_logger(__name__)


async def build_rag_context(
    user_id: str,
    query: str,
    openai_key: str | None,
) -> str:
    """Retrieve relevant chunks and return them as a formatted context string.

    Returns empty string when no key is provided, no chunks are found,
    or retrieval fails. Never raises.
    """
    if not openai_key:
        return ""
    try:
        chunks = await _retriever.retrieve_context(query, user_id, openai_key)
        if not chunks:
            return ""
        logger.info(
            "rag_context_built",
            user_id=user_id,
            chunk_count=len(chunks),
        )
        return _format_chunks(chunks)
    except Exception:
        logger.warning("rag_context_build_failed", exc_info=True)
        return ""


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    lines = ["[Knowledge Base Context]"]
    for chunk in chunks:
        lines.append(
            f'Document: "{chunk.document_name}" (relevance: {chunk.score:.2f})'
        )
        lines.append(chunk.content)
        lines.append("")
    lines.append(
        "Use the above context to answer the user's question. "
        "Cite document names when referencing this content."
    )
    return "\n".join(lines)
