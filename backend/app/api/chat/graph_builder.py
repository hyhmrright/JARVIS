"""LangGraph compilation and tool-loading helpers for the chat API."""

import asyncio
from pathlib import Path

import structlog
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import select

from app.agent.graph import create_graph
from app.core.config import settings
from app.core.llm_config import AgentConfig
from app.db.models import InstalledPlugin
from app.db.session import AsyncSessionLocal
from app.plugins import plugin_registry

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


async def load_personal_plugin_tools(user_id: str) -> list[BaseTool]:
    """Load personal installed skill_md/python_plugin tools for this request."""
    try:
        from app.plugins.loader import _load_from_directory, load_markdown_skills
        from app.plugins.registry import PluginRegistry

        personal_dir = Path(settings.installed_plugins_dir) / "users" / str(user_id)
        if not personal_dir.exists():
            return []

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(InstalledPlugin).where(
                    InstalledPlugin.scope == "personal",
                    InstalledPlugin.installed_by == user_id,
                    InstalledPlugin.type.in_(["skill_md", "python_plugin"]),
                )
            )
            rows = result.scalars().all()
            if not rows:
                return []

        personal_registry = PluginRegistry()
        _load_from_directory(personal_registry, personal_dir)
        await load_markdown_skills(personal_registry, [personal_dir])
        return personal_registry.get_all_tools()
    except Exception:
        logger.exception("personal_plugin_load_failed", user_id=user_id)
        return []


async def load_tools(enabled_tools: list[str] | None) -> tuple[list, list | None]:
    """Load MCP and plugin tools based on the user's enabled_tools config."""
    mcp_tools: list = []
    if enabled_tools is None or "mcp" in enabled_tools:
        from app.tools.mcp_client import create_mcp_tools, parse_mcp_configs

        mcp_tools = await create_mcp_tools(parse_mcp_configs(settings.mcp_servers_json))

    plugin_tools: list | None = None
    if enabled_tools is None or "plugin" in enabled_tools:
        plugin_tools = plugin_registry.get_all_tools() or None

    return mcp_tools, plugin_tools


async def load_all_tools(
    user_id: str, enabled_tools: list[str] | None
) -> tuple[list, list | None]:
    """Load MCP, plugin, and personal plugin tools concurrently."""
    (mcp_tools, plugin_tools), personal_tools = await asyncio.gather(
        load_tools(enabled_tools),
        load_personal_plugin_tools(user_id),
    )
    if personal_tools:
        plugin_tools = [*(plugin_tools or []), *personal_tools]
    return mcp_tools, plugin_tools
