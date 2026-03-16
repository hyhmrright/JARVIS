from typing import Annotated, Any, TypedDict

import structlog
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from app.agent.llm import get_llm

logger = structlog.get_logger(__name__)


# Generic state for compiled workflows
class WorkflowState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    context: dict[str, Any]
    next_node: str | None


# DSL Schema
class WorkflowNodeDSL(BaseModel):
    id: str
    type: str
    data: dict[str, Any]


class WorkflowEdgeDSL(BaseModel):
    id: str
    source: str
    target: str
    source_handle: str | None = Field(None, alias="sourceHandle")
    target_handle: str | None = Field(None, alias="targetHandle")


class WorkflowDSL(BaseModel):
    nodes: list[WorkflowNodeDSL]
    edges: list[WorkflowEdgeDSL]


class GraphCompiler:
    def __init__(self, dsl: WorkflowDSL, llm_config: dict[str, Any]):
        self.dsl = dsl
        self.llm_config = llm_config

    async def _llm_node_handler(
        self, state: WorkflowState, node_id: str
    ) -> dict[str, Any]:
        node = next(n for n in self.dsl.nodes if n.id == node_id)
        model = node.data.get("model", "deepseek-chat")
        prompt = node.data.get("prompt", "")

        llm = get_llm(
            provider=self.llm_config["provider"],
            model=model,
            api_key=self.llm_config["api_key"],
            base_url=self.llm_config.get("base_url"),
        )

        messages = state["messages"]
        if prompt:
            # Inject system prompt if defined in node
            messages = [SystemMessage(content=prompt)] + messages

        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    def compile(self) -> CompiledStateGraph:
        builder = StateGraph(WorkflowState)

        # Add Nodes
        for node in self.dsl.nodes:
            if node.type == "llm":
                # Use a closure or partial to pass node_id
                async def handle(
                    state: WorkflowState, nid: str = node.id
                ) -> dict[str, Any]:
                    return await self._llm_node_handler(state, nid)

                builder.add_node(node.id, handle)
            elif node.type == "input":
                # Entry point
                builder.add_node(node.id, lambda state: {"messages": []})
            else:
                # Default identity node for unknown types
                builder.add_node(node.id, lambda state: state)
        # Add Edges
        for edge in self.dsl.edges:
            # Basic linear edges for now
            builder.add_edge(edge.source, edge.target)

        # Find entry point
        start_node = next((n for n in self.dsl.nodes if n.type == "input"), None)
        if start_node:
            builder.add_edge(START, start_node.id)
        else:
            # Fallback to first node if no input node defined
            if self.dsl.nodes:
                builder.add_edge(START, self.dsl.nodes[0].id)

        # Auto-end leaf nodes
        node_ids = {n.id for n in self.dsl.nodes}
        source_ids = {e.source for e in self.dsl.edges}
        leaf_nodes = node_ids - source_ids
        for ln in leaf_nodes:
            builder.add_edge(ln, END)

        return builder.compile()
