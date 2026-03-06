from dataclasses import dataclass

import structlog
from langchain_core.messages import BaseMessage, SystemMessage
from qdrant_client.http.exceptions import UnexpectedResponse

from app.infra.qdrant import get_qdrant_client, user_collection_name
from app.rag.embedder import get_embedder

logger = structlog.get_logger(__name__)

_DEFAULT_TOP_K = 5
_DEFAULT_SCORE_THRESHOLD = 0.7


@dataclass
class RetrievedChunk:
    document_name: str
    content: str
    score: float


async def retrieve_context(
    query: str,
    user_id: str,
    openai_api_key: str,
    top_k: int = _DEFAULT_TOP_K,
    score_threshold: float = _DEFAULT_SCORE_THRESHOLD,
) -> list[RetrievedChunk]:
    """Search the user's Qdrant collection and return relevant chunks.

    Returns empty list (never raises) on missing collection or errors.
    """
    try:
        client = await get_qdrant_client()
        embedder = get_embedder(openai_api_key)
        query_vec = await embedder.aembed_query(query)
        hits = await client.search(  # type: ignore[attr-defined]
            collection_name=user_collection_name(user_id),
            query_vector=query_vec,
            limit=top_k,
            score_threshold=score_threshold,
        )
    except UnexpectedResponse as exc:
        if exc.status_code == 404:
            return []
        logger.warning("retriever_qdrant_error", user_id=user_id, error=str(exc))
        return []
    except Exception:
        logger.warning("retriever_unexpected_error", user_id=user_id, exc_info=True)
        return []

    return [
        RetrievedChunk(
            document_name=hit.payload.get("doc_name", "Unknown document"),
            content=hit.payload.get("text", ""),
            score=hit.score,
        )
        for hit in hits
        if hit.payload
    ]


async def maybe_inject_rag_context(
    messages: list[BaseMessage],
    query: str,
    user_id: str,
    openai_key: str | None,
) -> list[BaseMessage]:
    """Return messages with RAG context inserted at position 1, if available.

    Silently returns the original list when messages is empty, no key is
    provided, no chunks are found, or retrieval fails.
    """
    if not messages or not openai_key:
        return messages
    try:
        chunks = await retrieve_context(query, user_id, openai_key)
        if chunks:
            rag_msg = SystemMessage(content=format_rag_context(chunks))
            logger.info(
                "rag_context_injected",
                user_id=user_id,
                chunk_count=len(chunks),
            )
            return [messages[0], rag_msg, *messages[1:]]
    except Exception:
        logger.warning("rag_auto_inject_failed", exc_info=True)
    return messages


def format_rag_context(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks into a system message content block."""
    if not chunks:
        return ""
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
