from collections.abc import Callable, Coroutine
from typing import Annotated, Any, TypedDict

import structlog
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from app.agent.llm import get_llm

logger = structlog.get_logger(__name__)


# Generic state for compiled workflows
class GraphState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    node_outputs: dict[str, Any]  # keyed by node_id


# Keep WorkflowState as alias for backwards compatibility
WorkflowState = GraphState


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
    edges: list[WorkflowEdgeDSL] = []


class GraphCompiler:
    def __init__(self, dsl: WorkflowDSL, llm_config: dict[str, Any]) -> None:
        self.dsl = dsl
        self.llm_config = llm_config
        self._tools: list[BaseTool] = llm_config.get("tools") or []
        self._api_key: str | None = llm_config.get("api_key")

    def _render_template(self, template: str, node_outputs: dict[str, Any]) -> str:
        """Render a Jinja2 template with node_outputs as context."""
        from jinja2.sandbox import SandboxedEnvironment

        env = SandboxedEnvironment()
        ctx = {
            "nodes": {k: {"output": v} for k, v in node_outputs.items()},
        }
        try:
            return env.from_string(template).render(**ctx)
        except Exception:
            return template

    def _make_llm_node(
        self, node: WorkflowNodeDSL
    ) -> Callable[[GraphState], Coroutine[Any, Any, dict[str, Any]]]:
        node_id = node.id
        model = node.data.get("model", "deepseek-chat")
        prompt_template = node.data.get("prompt", "")
        provider = self.llm_config.get("provider", "deepseek")
        api_key = self._api_key or ""
        base_url = self.llm_config.get("base_url")

        async def handler(state: GraphState) -> dict[str, Any]:
            llm = get_llm(
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
            )
            node_outputs = state.get("node_outputs") or {}
            messages: list[BaseMessage] = list(state["messages"])
            if prompt_template:
                rendered = self._render_template(prompt_template, node_outputs)
                messages = [SystemMessage(content=rendered), *messages]

            response = await llm.ainvoke(messages)
            result_text = getattr(response, "content", str(response))
            new_outputs = dict(node_outputs)
            new_outputs[node_id] = result_text
            return {
                "messages": [response],
                "node_outputs": new_outputs,
            }

        return handler

    def _make_output_node(self, node_id: str) -> Callable[[GraphState], dict[str, Any]]:
        def handler(state: GraphState) -> dict[str, Any]:
            last_content = ""
            if state.get("messages"):
                last_msg = state["messages"][-1]
                last_content = getattr(last_msg, "content", str(last_msg))
            new_outputs = dict(state.get("node_outputs") or {})
            new_outputs[node_id] = last_content
            return {"node_outputs": new_outputs}

        return handler

    def _make_tool_node(
        self, node_id: str, tool_name: str
    ) -> Callable[[GraphState], Coroutine[Any, Any, dict[str, Any]]]:
        async def handler(state: GraphState) -> dict[str, Any]:
            tool: BaseTool | None = next(
                (t for t in (self._tools or []) if t.name == tool_name), None
            )
            last_content = ""
            if state.get("messages"):
                last_content = getattr(state["messages"][-1], "content", "")
            if tool is None:
                result = f"Error: tool '{tool_name}' not found"
            else:
                try:
                    result = await tool.arun(last_content)
                except Exception as exc:
                    result = f"Tool error: {exc}"
            new_outputs = dict(state.get("node_outputs") or {})
            new_outputs[node_id] = result
            return {
                "messages": [*state["messages"], AIMessage(content=result)],
                "node_outputs": new_outputs,
            }

        return handler

    def _make_image_gen_node(
        self, node_id: str, prompt_template: str
    ) -> Callable[[GraphState], Coroutine[Any, Any, dict[str, Any]]]:
        api_key = self._api_key

        async def handler(state: GraphState) -> dict[str, Any]:
            node_outputs = state.get("node_outputs") or {}
            rendered = self._render_template(prompt_template, node_outputs)
            from app.tools.image_gen_tool import create_image_gen_tool

            img_tool = create_image_gen_tool(api_key)
            if img_tool:
                try:
                    result = await img_tool.arun(rendered)
                except Exception as exc:
                    result = f"Image gen error: {exc}"
            else:
                result = "Error: OpenAI API key required for image generation"
            new_outputs = dict(node_outputs)
            new_outputs[node_id] = result
            return {
                "messages": [*state["messages"], AIMessage(content=result)],
                "node_outputs": new_outputs,
            }

        return handler

    def _make_condition_router(
        self, expr: str, true_target: str, false_target: str
    ) -> Callable[[GraphState], str]:
        def router(state: GraphState) -> str:
            node_outputs = state.get("node_outputs") or {}
            rendered = self._render_template(expr, node_outputs).strip().lower()
            return true_target if rendered in ("true", "1", "yes") else false_target

        return router

    # ------------------------------------------------------------------
    # compile() helpers — each keeps complexity low
    # ------------------------------------------------------------------

    @staticmethod
    def _input_handler(state: GraphState) -> dict[str, Any]:
        return {"node_outputs": state.get("node_outputs") or {}}

    def _add_nodes(self, graph: StateGraph) -> None:
        for node in self.dsl.nodes:
            if node.type == "input":
                graph.add_node(node.id, self._input_handler)
            elif node.type == "llm":
                llm_fn: Any = self._make_llm_node(node)
                graph.add_node(node.id, llm_fn)
            elif node.type == "output":
                out_fn: Any = self._make_output_node(node.id)
                graph.add_node(node.id, out_fn)
            elif node.type == "tool":
                tool_fn: Any = self._make_tool_node(
                    node.id, node.data.get("tool_name", "")
                )
                graph.add_node(node.id, tool_fn)
            elif node.type == "image_gen":
                img_fn: Any = self._make_image_gen_node(
                    node.id, node.data.get("prompt", "")
                )
                graph.add_node(node.id, img_fn)
            elif node.type == "condition":
                pass  # condition nodes become routers, not graph nodes
            else:
                graph.add_node(node.id, lambda s: s)

    def _add_condition_edges(self, graph: StateGraph) -> None:
        for node in self.dsl.nodes:
            if node.type != "condition":
                continue
            true_tgts = [
                e.target
                for e in self.dsl.edges
                if e.source == node.id and e.source_handle == "true"
            ]
            false_tgts = [
                e.target
                for e in self.dsl.edges
                if e.source == node.id and e.source_handle == "false"
            ]
            t_tgt = str(true_tgts[0] if true_tgts else END)
            f_tgt = str(false_tgts[0] if false_tgts else END)
            expr = str(node.data.get("condition_expression", "{{ false }}"))
            router = self._make_condition_router(expr, t_tgt, f_tgt)
            path_map: dict[str, str] = {t_tgt: t_tgt, f_tgt: f_tgt}
            for inc_edge in (e for e in self.dsl.edges if e.target == node.id):
                graph.add_conditional_edges(inc_edge.source, router, path_map)  # type: ignore[arg-type]

    def _add_regular_edges(self, graph: StateGraph, condition_ids: set[str]) -> None:
        for edge in self.dsl.edges:
            if edge.source in condition_ids:
                continue
            tgt = next((n for n in self.dsl.nodes if n.id == edge.target), None)
            if tgt and tgt.type == "condition":
                continue
            graph.add_edge(edge.source, edge.target)

    def _add_entry_edge(self, graph: StateGraph) -> None:
        entry = next((n for n in self.dsl.nodes if n.type == "input"), None)
        if entry:
            graph.add_edge(START, entry.id)
        elif self.dsl.nodes:
            graph.add_edge(START, self.dsl.nodes[0].id)

    def _is_leaf(self, node: WorkflowNodeDSL) -> bool:
        """True when node has no outgoing edges and no conditional targets."""
        has_outgoing = any(e.source == node.id for e in self.dsl.edges)
        if has_outgoing:
            return False
        # Also not a leaf if it's targeted by a condition node's routing
        return not any(
            n.type == "condition"
            and any(e.target == node.id for e in self.dsl.edges if e.source == n.id)
            for n in self.dsl.nodes
        )

    def _add_end_edges(self, graph: StateGraph) -> None:
        for node in self.dsl.nodes:
            if node.type != "condition" and self._is_leaf(node):
                graph.add_edge(node.id, END)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def compile(self) -> CompiledStateGraph:
        graph: StateGraph = StateGraph(GraphState)
        condition_source_ids = {n.id for n in self.dsl.nodes if n.type == "condition"}

        self._add_nodes(graph)
        self._add_condition_edges(graph)
        self._add_regular_edges(graph, condition_source_ids)
        self._add_entry_edge(graph)
        self._add_end_edges(graph)

        return graph.compile()
