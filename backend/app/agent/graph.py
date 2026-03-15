import structlog
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.agent.llm import get_llm_with_fallback
from app.agent.state import AgentState
from app.tools.browser_tool import browser_click, browser_navigate, browser_screenshot
from app.tools.code_exec_tool import execute_code
from app.tools.datetime_tool import get_datetime
from app.tools.file_tool import create_file_tools
from app.tools.memory_tool import read_memory_file, search_local_memory
from app.tools.rag_tool import create_rag_search_tool
from app.tools.search_tool import create_web_search_tool
from app.tools.shell_tool import shell_exec
from app.tools.web_fetch_tool import web_fetch

_TOOL_MAP = {
    "browser": browser_navigate,
    "browser_screenshot": browser_screenshot,
    "browser_click": browser_click,
    "code_exec": execute_code,
    "datetime": get_datetime,
    "shell": shell_exec,
    "web_fetch": web_fetch,
    "search_local_memory": search_local_memory,
    "read_memory_file": read_memory_file,
}

_DEFAULT_TOOLS = list(_TOOL_MAP.values())
logger = structlog.get_logger(__name__)
_SENSITIVE_TOOLS = ("shell", "code_exec", "file_delete", "file_write")


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
    base_url: str | None = None,
) -> list[BaseTool]:
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
                base_url=base_url,
            )
        )

    if user_id and (enabled_tools is None or "cron" in enabled_tools):
        from app.tools.cron_tool import create_cron_tools

        tools.extend(create_cron_tools(user_id))

    if enabled_tools is not None and "canvas" in enabled_tools and conversation_id:
        from app.tools.canvas_tool import create_canvas_tool

        tools.append(create_canvas_tool(conversation_id))

    if mcp_tools and (enabled_tools is None or "mcp" in enabled_tools):
        tools.extend(mcp_tools)

    if plugin_tools and (enabled_tools is None or "plugin" in enabled_tools):
        tools.extend(plugin_tools)

    return tools


def create_graph(  # noqa: C901
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
    base_url: str | None = None,
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
        base_url=base_url,
    )

    llm = get_llm_with_fallback(provider, model, all_keys[0], base_url=base_url)
    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    async def call_llm(state: AgentState) -> dict:
        response = await llm_with_tools.ainvoke(state.messages)
        return {"messages": [response]}

    def should_use_tool(state: AgentState) -> str:
        last = state.messages[-1]
        if not (hasattr(last, "tool_calls") and last.tool_calls):
            return END
        for tc in last.tool_calls:
            if any(s in tc["name"] for s in _SENSITIVE_TOOLS):
                if state.approved is None:
                    return "approval"
                if state.approved is False:
                    return END
        return "tools"

    async def ask_approval(state: AgentState) -> dict:
        last_msg = state.messages[-1]
        tool_calls = last_msg.tool_calls if isinstance(last_msg, AIMessage) else []
        return {"pending_tool_call": tool_calls[0] if tool_calls else None}

    async def review_output(state: AgentState) -> dict:
        """Self-Correction Node (Reflection)"""
        last = state.messages[-1]
        # In a full implementation, this uses an LLM as a Critic.
        # Here we mock a basic check: if answer seems too short, append a
        # self-correction prompt.
        is_ai = isinstance(last, AIMessage)
        if is_ai and not last.tool_calls and len(last.content) < 10:
            # We don't actually trigger another LLM call in this mock to
            # save tokens/time, but this establishes the routing architecture.
            pass
        return {}

    graph: StateGraph[AgentState] = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", tool_node)
    graph.add_node("approval", ask_approval)
    graph.add_node("review", review_output)

    graph.add_edge(START, "llm")

    # After LLM, decide to use tools, ask approval, or review
    def post_llm_route(state: AgentState) -> str:
        last = state.messages[-1]
        if not (hasattr(last, "tool_calls") and last.tool_calls):
            return "review"
        for tc in last.tool_calls:
            if any(s in tc["name"] for s in _SENSITIVE_TOOLS):
                if state.approved is None:
                    return "approval"
                if state.approved is False:
                    return END
        return "tools"

    graph.add_conditional_edges(
        "llm",
        post_llm_route,
        {"tools": "tools", "approval": "approval", "review": "review", END: END},
    )
    graph.add_edge("tools", "llm")
    graph.add_edge("review", END)

    return graph.compile()
