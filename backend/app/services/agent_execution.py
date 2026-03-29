"""Unified agent execution service.

Before this module, agent execution logic was duplicated in:
  - app/api/chat/routes.py::chat_stream()  (streaming path)
  - app/gateway/router.py::_run_agent()    (channel gateway path)
  - app/gateway/agent_runner.py::run_agent_for_user()  (cron/webhook path)

This service owns the *blocking* execution path.  The streaming path still
lives in routes.py because it is tightly coupled to SSE formatting,
per-chunk message persistence, and FastAPI's disconnect detection.
"""

from __future__ import annotations

import structlog
from langchain_core.messages import BaseMessage, ToolMessage

from app.agent.graph import create_graph
from app.core.llm_config import AgentConfig

logger = structlog.get_logger(__name__)


class AgentExecutionService:
    """Run the JARVIS agent graph in blocking (non-streaming) mode."""

    async def run_blocking(
        self,
        messages: list[BaseMessage],
        config: AgentConfig,
    ) -> str:
        """Invoke the agent graph and return the final AI message content.

        Raises:
            ValueError: if the graph returns no messages.
        """
        from app.agent.state import AgentState

        graph = create_graph(config)
        result = await graph.ainvoke(AgentState(messages=messages))

        result_messages = result.get("messages", [])
        if not result_messages:
            raise ValueError(
                f"Agent graph returned no messages for user_id={config.user_id}"
            )

        ai_content = str(result_messages[-1].content)

        tools_used = [
            m.name for m in result_messages if isinstance(m, ToolMessage) and m.name
        ]
        seen: set[str] = set()
        tools_used = [t for t in tools_used if not (t in seen or seen.add(t))]  # type: ignore[func-returns-value]

        logger.info(
            "agent_execution_completed",
            user_id=config.user_id,
            reply_chars=len(ai_content),
            tools_used=tools_used,
        )
        return ai_content
