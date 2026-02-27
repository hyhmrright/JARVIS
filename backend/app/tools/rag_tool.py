"""RAG knowledge base search tool for the LangGraph agent."""

import structlog
from langchain_core.tools import BaseTool, tool
from qdrant_client.http.exceptions import UnexpectedResponse

from app.rag.indexer import search_documents

logger = structlog.get_logger(__name__)


def create_rag_search_tool(user_id: str, openai_api_key: str) -> BaseTool:
    """Factory that returns a RAG search tool closed over user context.

    The tool needs ``user_id`` to locate the user's Qdrant collection and
    ``openai_api_key`` to generate query embeddings.
    """

    @tool
    async def rag_search(query: str) -> str:
        """Search the user's uploaded knowledge base documents.

        Use this when the user asks about content from their uploaded files
        or documents. query is a natural language search phrase.
        """
        try:
            results = await search_documents(user_id, query, openai_api_key, top_k=5)
        except UnexpectedResponse as e:
            if e.status_code == 404:
                return "No documents have been uploaded yet. Upload documents first to use knowledge base search."
            logger.exception("rag_search_error", user_id=user_id)
            return "Error: failed to search the knowledge base."
        except Exception:
            logger.exception("rag_search_error", user_id=user_id)
            return "Error: failed to search the knowledge base."

        if not results:
            return "No relevant documents found in the knowledge base."

        numbered = [f"[{i + 1}] {text}" for i, text in enumerate(results)]
        return "\n\n".join(numbered)

    return rag_search
