"""RAG knowledge base search tool for the LangGraph agent."""

import structlog
from langchain_core.tools import BaseTool, tool

from app.rag.retriever import retrieve_context

logger = structlog.get_logger(__name__)


def create_rag_search_tool(user_id: str, openai_api_key: str) -> BaseTool:
    """Factory that returns a RAG search tool closed over user context."""

    @tool
    async def rag_search(query: str) -> str:
        """Search the user's uploaded knowledge base documents.

        Use this when the user asks about content from their uploaded files
        or documents. query is a natural language search phrase.
        """
        try:
            chunks = await retrieve_context(query, user_id, openai_api_key)
        except Exception:
            logger.exception("rag_search_error", user_id=user_id)
            return "Error: failed to search the knowledge base."

        if not chunks:
            return "No relevant documents found in the knowledge base."

        parts = [
            f'[{i + 1}] Document: "{c.document_name}"'
            f" (relevance: {c.score:.2f})\n{c.content}"
            for i, c in enumerate(chunks)
        ]
        return "\n\n".join(parts)

    return rag_search
