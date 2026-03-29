"""Shared LLM configuration dataclasses.

``ResolvedLLMConfig`` is the canonical representation of a resolved LLM
provider configuration.  It was originally defined in ``app.api.deps``; it
now lives here so that non-API layers (agent, gateway, …) can import it
without pulling in FastAPI/SQLAlchemy dependencies.

``AgentConfig`` bundles every parameter needed to compile and run a
LangGraph agent into a single typed object, replacing the long flat
keyword-argument lists that were previously threaded through
``build_expert_graph`` and ``create_graph``.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ResolvedLLMConfig:
    """Immutable container for resolved LLM provider settings."""

    provider: str
    model_name: str
    api_key: str
    api_keys: list[str]
    enabled_tools: list[str] | None
    persona_override: str | None
    raw_keys: dict[str, Any]
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    system_prompt: str | None = None


@dataclass
class AgentConfig:
    """All parameters needed to compile and run a LangGraph agent."""

    llm: ResolvedLLMConfig
    user_id: str | None = None
    conversation_id: str | None = None
    depth: int = 0
    mcp_tools: list = field(default_factory=list)
    plugin_tools: list = field(default_factory=list)
    openai_api_key: str | None = None
    tavily_api_key: str | None = None
    workflow_dsl: dict | None = None  # set when conversation has workflow DSL
