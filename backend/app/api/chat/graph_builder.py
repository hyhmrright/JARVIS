"""LangGraph compilation helpers for the chat API."""

import structlog
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import create_graph
from app.core.llm_config import AgentConfig

logger = structlog.get_logger(__name__)


def build_expert_graph(route: str, config: AgentConfig) -> CompiledStateGraph:
    """Return the appropriate compiled LangGraph for the given routing label.

    Expert agents (code/research/writing) each select a focused tool subset.
    Workflow DSLs take precedence over default agents.
    Unknown labels fall back to the standard ReAct graph with all enabled tools.
    """
    if config.workflow_dsl:
        from app.agent.compiler import GraphCompiler, WorkflowDSL

        compiler = GraphCompiler(
            dsl=WorkflowDSL(**config.workflow_dsl),
            llm_config={
                "provider": config.llm.provider,
                "api_key": config.llm.api_key,
                "base_url": config.llm.base_url,
                "temperature": config.llm.temperature,
                **(
                    {"max_tokens": config.llm.max_tokens}
                    if config.llm.max_tokens
                    else {}
                ),
            },
        )
        return compiler.compile()

    from app.agent.experts import (
        create_code_agent_graph,
        create_research_agent_graph,
        create_writing_agent_graph,
    )

    if route == "code":
        return create_code_agent_graph(
            provider=config.llm.provider,
            model=config.llm.model_name,
            api_key=config.llm.api_key,
            user_id=config.user_id,
            openai_api_key=config.openai_api_key,
            api_keys=config.llm.api_keys,
            mcp_tools=config.mcp_tools or None,
            plugin_tools=config.plugin_tools or None,
            conversation_id=config.conversation_id,
            base_url=config.llm.base_url,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )
    if route == "research":
        return create_research_agent_graph(
            provider=config.llm.provider,
            model=config.llm.model_name,
            api_key=config.llm.api_key,
            user_id=config.user_id,
            openai_api_key=config.openai_api_key,
            tavily_api_key=config.tavily_api_key,
            api_keys=config.llm.api_keys,
            mcp_tools=config.mcp_tools or None,
            plugin_tools=config.plugin_tools or None,
            conversation_id=config.conversation_id,
            base_url=config.llm.base_url,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )
    if route == "writing":
        return create_writing_agent_graph(
            provider=config.llm.provider,
            model=config.llm.model_name,
            api_key=config.llm.api_key,
            user_id=config.user_id,
            openai_api_key=config.openai_api_key,
            api_keys=config.llm.api_keys,
            mcp_tools=config.mcp_tools or None,
            plugin_tools=config.plugin_tools or None,
            conversation_id=config.conversation_id,
            base_url=config.llm.base_url,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )
    return create_graph(config)
