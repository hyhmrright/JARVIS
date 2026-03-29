# backend/app/agent/interfaces.py
"""Abstract interfaces for the agent layer.

Defining these in a separate module avoids circular imports:
  agent/graph.py  ->  tools/subagent_tool.py
  tools/subagent_tool.py  ->  agent/graph.py  (previously circular)

After this change:
  tools/subagent_tool.py  ->  agent/interfaces.py  (no cycle)
  agent/graph.py          ->  (unchanged, still concrete)
  app/main.py             ->  injects ConcreteFactory at startup
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage
    from langgraph.graph.state import CompiledStateGraph


@runtime_checkable
class AgentGraphFactory(Protocol):
    """Structural protocol for creating a compiled LangGraph agent graph.

    Consumers (e.g., subagent_tool) depend on this interface, not on the
    concrete ``agent/graph.py`` module.  The concrete implementation is
    injected at application startup via ``app/main.py``.
    """

    async def create(
        self,
        messages: list[BaseMessage],
        config: object,  # AgentConfig — typed as object to avoid circular import
    ) -> CompiledStateGraph: ...
