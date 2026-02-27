import structlog
from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.agent.llm import get_llm
from app.agent.state import AgentState
from app.tools.code_exec_tool import execute_code
from app.tools.datetime_tool import get_datetime
from app.tools.rag_tool import create_rag_search_tool
from app.tools.search_tool import web_search

# 工具名称 → 工具对象的映射（与 UserSettings.enabled_tools 的值对应）
# NOTE: "rag_search" is not in this map because it requires per-request
# user context (user_id + openai_api_key) and is created dynamically.
_TOOL_MAP = {
    "search": web_search,
    "code_exec": execute_code,
    "datetime": get_datetime,
}

_DEFAULT_TOOLS = list(_TOOL_MAP.values())

logger = structlog.get_logger(__name__)


def create_graph(
    provider: str,
    model: str,
    api_key: str,
    enabled_tools: list[str] | None = None,
    *,
    user_id: str | None = None,
    openai_api_key: str | None = None,
) -> CompiledStateGraph:
    if enabled_tools is not None:
        tools = [_TOOL_MAP[name] for name in enabled_tools if name in _TOOL_MAP]
    else:
        tools = list(_DEFAULT_TOOLS)

    # Dynamically create RAG search tool when user context is available
    if (
        user_id
        and openai_api_key
        and (enabled_tools is None or "rag_search" in enabled_tools)
    ):
        tools.append(create_rag_search_tool(user_id, openai_api_key))

    llm = get_llm(provider, model, api_key)
    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    async def call_llm(state: AgentState) -> dict[str, list[BaseMessage]]:
        response = await llm_with_tools.ainvoke(state.messages)
        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_names = [tc["name"] for tc in response.tool_calls]
            logger.info("agent_tool_calls", tools=tool_names)
        else:
            logger.info("agent_llm_response", content_chars=len(str(response.content)))
        return {"messages": [response]}

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
