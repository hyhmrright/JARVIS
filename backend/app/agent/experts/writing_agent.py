"""WritingAgent — specialised for drafting, editing, and summarizing text."""

from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import create_graph

_WRITING_TOOLS = ["rag_search", "web_fetch", "datetime"]


def create_writing_agent_graph(
    *,
    provider: str,
    model: str,
    api_key: str,
    user_id: str | None = None,
    openai_api_key: str | None = None,
    api_keys: list[str] | None = None,
    mcp_tools: list[BaseTool] | None = None,
    plugin_tools: list[BaseTool] | None = None,
    conversation_id: str | None = None,
    fallback_providers: list[dict] | None = None,
    base_url: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> CompiledStateGraph:
    """Return a compiled LangGraph optimised for writing tasks.

    Includes rag_search (requires openai_api_key), web_fetch, and
    datetime tools. Excludes code execution, shell, and web search tools
    to focus on text work.
    MCP and plugin tools are forwarded when provided.
    """
    return create_graph(
        provider=provider,
        model=model,
        api_key=api_key,
        enabled_tools=_WRITING_TOOLS,
        user_id=user_id,
        openai_api_key=openai_api_key,
        api_keys=api_keys,
        mcp_tools=mcp_tools,
        plugin_tools=plugin_tools,
        conversation_id=conversation_id,
        fallback_providers=fallback_providers,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )
