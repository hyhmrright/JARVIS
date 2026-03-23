import asyncio
import string
from dataclasses import dataclass
from typing import Any

import structlog
from langchain_core.messages import BaseMessage, SystemMessage
from qdrant_client.http.exceptions import UnexpectedResponse

from app.infra.qdrant import get_qdrant_client, user_collection_name
from app.rag.embedder import get_embedder

logger = structlog.get_logger(__name__)

_DEFAULT_TOP_K = 5
_DEFAULT_SCORE_THRESHOLD = 0.7
_RERANK_CANDIDATE_MULTIPLIER = 3
_VECTOR_WEIGHT = 0.7
_KEYWORD_WEIGHT = 0.3
_PUNCT_TRANSLATOR = str.maketrans("", "", string.punctuation)


@dataclass
class RetrievedChunk:
    document_name: str
    content: str
    score: float


def _tokenize(text: str) -> set[str]:
    """Lowercase and strip punctuation, returning a set of word tokens."""
    return {w for w in text.lower().translate(_PUNCT_TRANSLATOR).split() if w}


def _keyword_score(query: str, text: str) -> float:
    """Compute keyword overlap: fraction of *unique* query words found in text.

    Both query and text are tokenized into sets (lower-cased, punctuation
    stripped), so duplicate query tokens are deduplicated before scoring.
    Result is always in [0, 1].
    """
    query_words = _tokenize(query)
    if not query_words:
        return 0.0
    text_words = _tokenize(text)
    if not text_words:
        return 0.0
    overlap = query_words & text_words
    return len(overlap) / len(query_words)


def _rerank(
    chunks: list[RetrievedChunk], query: str, top_k: int
) -> list[RetrievedChunk]:
    """Sort chunks by combined score and return top_k, updating chunk.score.

    Combined score = 70% vector score + 30% keyword overlap.
    chunk.score is updated to the combined score so that displayed
    relevance values are consistent with the final ranking order.
    """
    for chunk in chunks:
        chunk.score = _VECTOR_WEIGHT * chunk.score + _KEYWORD_WEIGHT * _keyword_score(
            query, chunk.content
        )
    chunks.sort(key=lambda c: c.score, reverse=True)
    return chunks[:top_k]


def _hits_to_chunks(hits: list[Any]) -> list[RetrievedChunk]:
    """Convert Qdrant search hits to RetrievedChunk list, skipping empty payloads."""
    return [
        RetrievedChunk(
            document_name=hit.payload.get("doc_name", "Unknown document"),
            content=hit.payload.get("text", ""),
            score=hit.score,
        )
        for hit in hits
        if hit.payload
    ]


async def retrieve_context(
    query: str,
    user_id: str,
    openai_api_key: str,
    top_k: int = _DEFAULT_TOP_K,
    score_threshold: float = _DEFAULT_SCORE_THRESHOLD,
) -> list[RetrievedChunk]:
    """Search the user's Qdrant collection and return the top-k chunks by score."""
    try:
        client = await get_qdrant_client()
        embedder = get_embedder(openai_api_key)
        query_vec = await embedder.aembed_query(query)
        collection = user_collection_name(user_id)

        hits = await client.search(  # type: ignore[attr-defined]
            collection_name=collection,
            query_vector=query_vec,
            limit=top_k * _RERANK_CANDIDATE_MULTIPLIER,
            score_threshold=score_threshold,
        )

        candidates = _hits_to_chunks(hits)
        return _rerank(candidates, query, top_k)

    except UnexpectedResponse as exc:
        if exc.status_code == 404:
            return []
        logger.warning("retriever_qdrant_error", user_id=user_id, error=str(exc))
        return []
    except Exception:
        logger.warning("retriever_unexpected_error", user_id=user_id, exc_info=True)
        return []


async def retrieve_context_multi(
    query: str,
    user_id: str,
    workspace_ids: list[str],
    openai_api_key: str,
    top_k: int = _DEFAULT_TOP_K,
    score_threshold: float = _DEFAULT_SCORE_THRESHOLD,
) -> list[RetrievedChunk]:
    """Search user personal collection plus workspace collections.

    Returns merged results sorted by combined score descending.
    Returns empty list (never raises) on any error.
    """
    collection_names = [user_collection_name(user_id)]
    collection_names.extend(f"workspace_{ws_id}" for ws_id in workspace_ids)

    try:
        client = await get_qdrant_client()
        embedder = get_embedder(openai_api_key)
        query_vec = await embedder.aembed_query(query)

        # Per-collection limit scales down with collection count so total
        # candidates ≈ top_k * _RERANK_CANDIDATE_MULTIPLIER regardless of N,
        # but never below top_k per collection to preserve quality.
        per_col_limit = max(
            top_k,
            top_k * _RERANK_CANDIDATE_MULTIPLIER // len(collection_names),
        )

        async def _search_one(collection_name: str) -> list[RetrievedChunk]:
            try:
                hits = await client.search(  # type: ignore[attr-defined]
                    collection_name=collection_name,
                    query_vector=query_vec,
                    limit=per_col_limit,
                    score_threshold=score_threshold,
                )
                return _hits_to_chunks(hits)
            except UnexpectedResponse as exc:
                if exc.status_code != 404:
                    logger.warning(
                        "retriever_qdrant_error",
                        collection=collection_name,
                        error=str(exc),
                    )
                return []
            except Exception:
                logger.warning(
                    "retriever_collection_error",
                    collection=collection_name,
                    exc_info=True,
                )
                return []

        results = await asyncio.gather(*(_search_one(c) for c in collection_names))
        all_chunks: list[RetrievedChunk] = [
            chunk for per_col in results for chunk in per_col
        ]
        return _rerank(all_chunks, query, top_k)
    except Exception:
        logger.warning(
            "retriever_multi_unexpected_error", user_id=user_id, exc_info=True
        )
        return []


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
    lines = ["[Knowledge Base Context]", ""]
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"[{i}] {chunk.document_name} (relevance: {chunk.score:.2f})")
        lines.append(chunk.content)
        lines.append("")
    source_list = ", ".join(
        f'[{i}] "{c.document_name}"' for i, c in enumerate(chunks, 1)
    )
    lines.append(
        "When using information from the context above, Cite document names "
        "inline using the reference numbers (e.g. [1], [2]). "
        f"Available sources: {source_list}."
    )
    return "\n".join(lines)
