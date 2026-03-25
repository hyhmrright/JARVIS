"""Supervisor pattern — decomposes a complex task into subtasks.

The supervisor graph follows a plan → execute → aggregate flow:

1. **plan_node**: The LLM breaks the user request into discrete subtasks.
2. **execute_node**: Each subtask is dispatched to a sub-agent.
3. **aggregate_node**: The LLM synthesises all sub-results into a final answer.
"""

from dataclasses import dataclass, field

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.llm import get_llm_with_fallback
from app.tools.subagent_tool import create_subagent_tool

logger = structlog.get_logger(__name__)

_PLAN_PROMPT = """\
You are a task planner. Break the following request into a numbered list of \
independent subtasks. Each subtask must be self-contained and actionable.

Reply ONLY with the numbered list (one subtask per line). No preamble."""

_AGGREGATE_PROMPT = """\
You are a results synthesiser. The user's original request and the results \
of each subtask are provided below. Combine them into a single, coherent \
final answer.

Reply with only the final answer."""


@dataclass(kw_only=True)
class SupervisorState:
    messages: list[BaseMessage] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)
    results: list[str] = field(default_factory=list)
    current_step: int = 0


def create_supervisor_graph(
    *,
    provider: str,
    model: str,
    api_key: str,
    api_keys: list[str] | None = None,
    user_id: str | None = None,
    openai_api_key: str | None = None,
    tavily_api_key: str | None = None,
    enabled_tools: list[str] | None = None,
    depth: int = 0,
    base_url: str | None = None,
) -> CompiledStateGraph:
    """Build a supervisor LangGraph that plans, executes, and aggregates."""
    llm = get_llm_with_fallback(provider, model, api_key, base_url=base_url)

    subagent = create_subagent_tool(
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

    async def plan_node(state: SupervisorState) -> dict:
        user_msg = state.messages[-1].content if state.messages else ""
        response = await llm.ainvoke(
            [
                SystemMessage(content=_PLAN_PROMPT),
                HumanMessage(content=str(user_msg)),
            ]
        )
        raw = str(response.content).strip()
        steps = [
            line.lstrip("0123456789.) ").strip()
            for line in raw.splitlines()
            if line.strip()
        ]
        logger.info("supervisor_plan", step_count=len(steps))
        return {"plan": steps, "current_step": 0, "results": []}

    async def execute_node(state: SupervisorState) -> dict:
        idx = state.current_step
        if idx >= len(state.plan):
            return {"current_step": idx}

        task = state.plan[idx]
        logger.info("supervisor_execute", step=idx, task_preview=task[:80])
        try:
            result = await subagent.ainvoke({"task": task})
        except Exception:
            logger.exception("supervisor_subtask_failed", step=idx)
            result = f"[Error: subtask {idx + 1} failed]"
        return {
            "results": [*state.results, str(result)],
            "current_step": idx + 1,
        }

    def should_continue(state: SupervisorState) -> str:
        if state.current_step < len(state.plan):
            return "execute"
        return "aggregate"

    async def aggregate_node(state: SupervisorState) -> dict:
        user_msg = state.messages[-1].content if state.messages else ""
        parts = [f"Original request: {user_msg}\n"]
        for i, (step, result) in enumerate(
            zip(state.plan, state.results, strict=False)
        ):
            parts.append(f"Subtask {i + 1}: {step}\nResult: {result}\n")
        combined = "\n".join(parts)

        response = await llm.ainvoke(
            [
                SystemMessage(content=_AGGREGATE_PROMPT),
                HumanMessage(content=combined),
            ]
        )
        final = str(response.content)
        logger.info("supervisor_aggregated", answer_chars=len(final))
        return {
            "messages": [
                *state.messages,
                AIMessage(content=final),
            ]
        }

    graph: StateGraph = StateGraph(SupervisorState)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("aggregate", aggregate_node)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "execute")
    graph.add_conditional_edges("execute", should_continue)
    graph.add_edge("aggregate", END)

    return graph.compile()
