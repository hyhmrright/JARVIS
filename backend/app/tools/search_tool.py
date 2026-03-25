"""Web search tool using Tavily Search API."""

import asyncio

import structlog
from langchain_core.tools import BaseTool, tool
from tavily import AsyncTavilyClient

from app.core.config import settings

logger = structlog.get_logger(__name__)

_DEFAULT_MAX_RESULTS = 5


async def _web_search_impl(
    query: str, api_key: str, max_results: int = _DEFAULT_MAX_RESULTS
) -> str:
    """Execute a Tavily web search and format results.

    Separated from the tool wrapper for testability.
    """
    client = AsyncTavilyClient(api_key=api_key)
    try:
        response = await asyncio.wait_for(
            client.search(query=query, max_results=max_results),
            timeout=settings.tool_search_timeout,
        )
    except TimeoutError:
        return "Search timed out. Please try again."

    results = response.get("results", [])
    if not results:
        return "No results found."

    formatted = []
    for i, item in enumerate(results, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        content = item.get("content", "")
        formatted.append(f"[{i}] {title}\n    {url}\n    {content}")

    return "\n\n".join(formatted)


def create_web_search_tool(api_key: str) -> BaseTool:
    """Factory that returns a web search tool closed over a Tavily API key."""

    @tool
    async def web_search(query: str) -> str:
        """Search the web for current information.

        Use this when the user asks about recent events, facts, or anything
        that may require up-to-date information from the internet.
        query is a natural language search phrase.
        """
        try:
            return await _web_search_impl(query, api_key)
        except Exception:
            logger.exception("web_search_error", query=query)
            return "Error: failed to perform web search."

    return web_search
