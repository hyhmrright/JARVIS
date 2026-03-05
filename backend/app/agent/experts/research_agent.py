"""ResearchAgent — specialised for knowledge retrieval and research tasks."""

from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import create_graph

# Note: "search" resolves to the Tavily web search tool only when
# tavily_api_key is provided; it is silently skipped otherwise.
_RESEARCH_TOOLS = ["rag_search", "search", "web_fetch", "datetime"]


def create_research_agent_graph(
    *,
    provider: str,
    model: str,
    api_key: str,
    user_id: str | None = None,
    openai_api_key: str | None = None,
    tavily_api_key: str | None = None,
    api_keys: list[str] | None = None,
    mcp_tools: list[BaseTool] | None = None,
    plugin_tools: list[BaseTool] | None = None,
    conversation_id: str | None = None,
    fallback_providers: list[dict] | None = None,
) -> CompiledStateGraph:
    """Return a compiled LangGraph optimised for research tasks.

    Includes rag_search (requires openai_api_key), web search
    (requires tavily_api_key), web_fetch, and datetime tools.
    Excludes code execution and shell tools.
    MCP and plugin tools are forwarded when provided.
    """
    return create_graph(
        provider=provider,
        model=model,
        api_key=api_key,
        enabled_tools=_RESEARCH_TOOLS,
        user_id=user_id,
        openai_api_key=openai_api_key,
        tavily_api_key=tavily_api_key,
        api_keys=api_keys,
        mcp_tools=mcp_tools,
        plugin_tools=plugin_tools,
        conversation_id=conversation_id,
        fallback_providers=fallback_providers,
    )
