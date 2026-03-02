import structlog
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.agent.llm import get_llm, get_llm_with_fallback
from app.agent.state import AgentState
from app.tools.browser_tool import browser_navigate
from app.tools.code_exec_tool import execute_code
from app.tools.datetime_tool import get_datetime
from app.tools.file_tool import create_file_tools
from app.tools.rag_tool import create_rag_search_tool
from app.tools.search_tool import create_web_search_tool
from app.tools.shell_tool import shell_exec
from app.tools.web_fetch_tool import web_fetch

# Static tools that need no per-request context
_TOOL_MAP = {
    "browser": browser_navigate,
    "code_exec": execute_code,
    "datetime": get_datetime,
    "shell": shell_exec,
    "web_fetch": web_fetch,
}

_DEFAULT_TOOLS = list(_TOOL_MAP.values())

logger = structlog.get_logger(__name__)

_ROTATABLE_ERROR_KEYWORDS = (
    "authentication",
    "rate limit",
    "rate_limit",
    "quota",
    "429",
    "401",
)


def _resolve_tools(
    enabled_tools: list[str] | None,
    *,
    user_id: str | None,
    openai_api_key: str | None,
    tavily_api_key: str | None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    api_keys: list[str] | None = None,
    depth: int = 0,
    mcp_tools: list[BaseTool] | None = None,
    plugin_tools: list[BaseTool] | None = None,
    conversation_id: str | None = None,
) -> list[BaseTool]:
    """Build the tool list based on enabled flags and available keys."""
    if enabled_tools is not None:
        tools = [_TOOL_MAP[name] for name in enabled_tools if name in _TOOL_MAP]
    else:
        tools = list(_DEFAULT_TOOLS)

    if tavily_api_key and (enabled_tools is None or "search" in enabled_tools):
        tools.append(create_web_search_tool(tavily_api_key))

    if (
        user_id
        and openai_api_key
        and (enabled_tools is None or "rag_search" in enabled_tools)
    ):
        tools.append(create_rag_search_tool(user_id, openai_api_key))

    if user_id and (enabled_tools is None or "file" in enabled_tools):
        tools.extend(create_file_tools(user_id))

    if (
        enabled_tools is not None
        and "subagent" in enabled_tools
        and provider
        and model
        and api_key
    ):
        from app.tools.subagent_tool import create_subagent_tool

        tools.append(
            create_subagent_tool(
                provider=provider,
                model=model,
                api_key=api_key,
                api_keys=api_keys,
                current_depth=depth,
                user_id=user_id,
                openai_api_key=openai_api_key,
                tavily_api_key=tavily_api_key,
                enabled_tools=enabled_tools,
            )
        )

    if user_id and (enabled_tools is None or "cron" in enabled_tools):
        from app.tools.cron_tool import create_cron_tools

        tools.extend(create_cron_tools(user_id))

    # Canvas tool -- opt-in only, requires conversation_id for event routing
    if enabled_tools is not None and "canvas" in enabled_tools and conversation_id:
        from app.tools.canvas_tool import create_canvas_tool

        tools.append(create_canvas_tool(conversation_id))

    if mcp_tools and (enabled_tools is None or "mcp" in enabled_tools):
        tools.extend(mcp_tools)

    if plugin_tools and (enabled_tools is None or "plugin" in enabled_tools):
        tools.extend(plugin_tools)

    return tools


def create_graph(
    provider: str,
    model: str,
    api_key: str,
    enabled_tools: list[str] | None = None,
    *,
    api_keys: list[str] | None = None,
    user_id: str | None = None,
    openai_api_key: str | None = None,
    tavily_api_key: str | None = None,
    depth: int = 0,
    mcp_tools: list[BaseTool] | None = None,
    plugin_tools: list[BaseTool] | None = None,
    conversation_id: str | None = None,
    fallback_providers: list[dict] | None = None,
) -> CompiledStateGraph:
    all_keys = api_keys if api_keys else [api_key]

    tools = _resolve_tools(
        enabled_tools,
        user_id=user_id,
        openai_api_key=openai_api_key,
        tavily_api_key=tavily_api_key,
        provider=provider,
        model=model,
        api_key=api_key,
        api_keys=api_keys,
        depth=depth,
        mcp_tools=mcp_tools,
        plugin_tools=plugin_tools,
        conversation_id=conversation_id,
    )

    llm = get_llm_with_fallback(provider, model, all_keys[0], fallback_providers)
    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    key_index = 0  # Track current key index via closure

    async def call_llm(state: AgentState) -> dict[str, list[BaseMessage]]:
        nonlocal llm_with_tools, key_index
        last_error: Exception | None = None
        attempts = len(all_keys)
        for _ in range(attempts):
            try:
                response = await llm_with_tools.ainvoke(state.messages)
                if hasattr(response, "tool_calls") and response.tool_calls:
                    tool_names = [tc["name"] for tc in response.tool_calls]
                    logger.info("agent_tool_calls", tools=tool_names)
                else:
                    logger.info(
                        "agent_llm_response",
                        content_chars=len(str(response.content)),
                    )
                return {"messages": [response]}
            except Exception as exc:
                error_str = str(exc).lower()
                is_rotatable = any(kw in error_str for kw in _ROTATABLE_ERROR_KEYWORDS)
                if is_rotatable and len(all_keys) > 1:
                    last_error = exc
                    key_index = (key_index + 1) % len(all_keys)
                    logger.warning(
                        "api_key_rotation",
                        provider=provider,
                        key_index=key_index,
                        error=str(exc)[:100],
                    )
                    new_llm = get_llm(provider, model, all_keys[key_index])
                    llm_with_tools = new_llm.bind_tools(tools)
                    continue
                raise
        raise last_error  # type: ignore[misc]

    def should_use_tool(state: AgentState) -> str:
        last = state.messages[-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph: StateGraph[AgentState] = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", should_use_tool)
    graph.add_edge("tools", "llm")
    return graph.compile()
