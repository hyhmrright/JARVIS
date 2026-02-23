from typing import Any

from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.llm import get_llm
from app.agent.state import AgentState
from app.tools.code_exec_tool import execute_code
from app.tools.datetime_tool import get_datetime
from app.tools.search_tool import web_search

TOOLS = [get_datetime, web_search, execute_code]


def create_graph(provider: str, model: str, api_key: str) -> Any:
    llm = get_llm(provider, model, api_key)
    llm_with_tools = llm.bind_tools(TOOLS)
    tool_node = ToolNode(TOOLS)

    async def call_llm(state: AgentState) -> dict[str, list[BaseMessage]]:
        response = await llm_with_tools.ainvoke(state.messages)
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
