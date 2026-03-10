"""CodeAgent — specialised for code generation, debugging, and execution."""

from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import create_graph

_CODE_TOOLS = ["code_exec", "shell", "file", "datetime"]


def create_code_agent_graph(
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
) -> CompiledStateGraph:
    """Return a compiled LangGraph optimised for coding tasks.

    Includes code_exec, shell, file, and datetime tools.
    Excludes browser, search, and RAG tools to keep focus on execution.
    MCP and plugin tools are forwarded when provided.
    """
    return create_graph(
        provider=provider,
        model=model,
        api_key=api_key,
        enabled_tools=_CODE_TOOLS,
        user_id=user_id,
        openai_api_key=openai_api_key,
        api_keys=api_keys,
        mcp_tools=mcp_tools,
        plugin_tools=plugin_tools,
        conversation_id=conversation_id,
        fallback_providers=fallback_providers,
        base_url=base_url,
    )
