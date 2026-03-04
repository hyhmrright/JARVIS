"""SubAgent tool — allows the main agent to spawn child agents for subtasks.

The factory function ``create_subagent_tool`` returns a LangChain tool bound
to the current conversation context.  When invoked, the tool creates an
independent LangGraph agent that runs to completion and returns its final
answer as a string.

A ``MAX_DEPTH`` guard prevents unbounded recursion.
"""

import structlog
from langchain_core.tools import BaseTool, tool

logger = structlog.get_logger(__name__)

MAX_DEPTH = 3


def create_subagent_tool(
    *,
    provider: str,
    model: str,
    api_key: str,
    api_keys: list[str] | None = None,
    current_depth: int = 0,
    user_id: str | None = None,
    openai_api_key: str | None = None,
    tavily_api_key: str | None = None,
    enabled_tools: list[str] | None = None,
) -> BaseTool:
    """Return a ``spawn_subagent`` tool pre-bound to the given context."""

    @tool
    async def spawn_subagent(task: str) -> str:
        """Delegate a subtask to an independent sub-agent.

        Use this when a task is complex enough to benefit from a dedicated
        agent that can reason and use tools independently.  The sub-agent
        receives the task description and returns its final answer.

        Args:
            task: A clear, self-contained description of the subtask.
        """
        if current_depth >= MAX_DEPTH:
            return (
                f"Cannot spawn sub-agent: maximum depth ({MAX_DEPTH}) reached. "
                "Please handle this task directly."
            )

        # Delayed import to avoid circular dependency (graph → tools → graph)
        from langchain_core.messages import HumanMessage, SystemMessage

        from app.agent.graph import create_graph
        from app.agent.state import AgentState

        logger.info(
            "subagent_spawned",
            depth=current_depth + 1,
            task_preview=task[:100],
        )

        sub_enabled = [t for t in (enabled_tools or []) if t != "subagent"]

        graph = create_graph(
            provider=provider,
            model=model,
            api_key=api_key,
            enabled_tools=sub_enabled or None,
            api_keys=api_keys,
            user_id=user_id,
            openai_api_key=openai_api_key,
            tavily_api_key=tavily_api_key,
        )

        try:
            result = await graph.ainvoke(
                AgentState(
                    messages=[
                        SystemMessage(
                            content="You are a focused sub-agent. Complete "
                            "the assigned task concisely and return the "
                            "result."
                        ),
                        HumanMessage(content=task),
                    ],
                    depth=current_depth + 1,
                )
            )
            answer = str(result["messages"][-1].content)
        except Exception:
            logger.exception(
                "subagent_invocation_failed",
                depth=current_depth + 1,
            )
            answer = "Sub-agent encountered an error processing this task."

        logger.info(
            "subagent_completed",
            depth=current_depth + 1,
            answer_chars=len(answer),
        )
        return answer

    return spawn_subagent
