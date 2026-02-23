from typing import Any

from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph

from app.agent.llm import get_llm
from app.agent.state import AgentState


def create_graph(provider: str, model: str, api_key: str) -> Any:
    llm = get_llm(provider, model, api_key)

    async def call_llm(state: AgentState) -> dict[str, list[BaseMessage]]:
        response = await llm.ainvoke(state.messages)
        return {"messages": [response]}

    graph: StateGraph[AgentState] = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_edge(START, "llm")
    graph.add_edge("llm", END)
    return graph.compile()
