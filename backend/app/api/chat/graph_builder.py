"""LangGraph compilation and tool-loading helpers for the chat API."""

from pathlib import Path

import structlog
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import select

from app.agent.graph import create_graph
from app.core.config import settings
from app.db.models import InstalledPlugin
from app.db.session import AsyncSessionLocal
from app.plugins import plugin_registry

logger = structlog.get_logger(__name__)


def build_expert_graph(
    route: str,
    *,
    provider: str,
    model: str,
    api_key: str,
    api_keys: list[str] | None,
    user_id: str,
    openai_api_key: str | None,
    tavily_api_key: str | None,
    enabled_tools: list[str] | None,
    mcp_tools: list,
    plugin_tools: list | None,
    conversation_id: str,
    base_url: str | None = None,
    workflow_dsl: dict | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> CompiledStateGraph:
    """Return the appropriate compiled LangGraph for the given routing label.

    Expert agents (code/research/writing) each select a focused tool subset.
    Workflow DSLs take precedence over default agents.
    Unknown labels fall back to the standard ReAct graph with all enabled tools.
    """
    if workflow_dsl:
        from app.agent.compiler import GraphCompiler, WorkflowDSL

        compiler = GraphCompiler(
            dsl=WorkflowDSL(**workflow_dsl),
            llm_config={
                "provider": provider,
                "api_key": api_key,
                "base_url": base_url,
                "temperature": temperature,
                **({"max_tokens": max_tokens} if max_tokens else {}),
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
            provider=provider,
            model=model,
            api_key=api_key,
            user_id=user_id,
            openai_api_key=openai_api_key,
            api_keys=api_keys,
            mcp_tools=mcp_tools,
            plugin_tools=plugin_tools,
            conversation_id=conversation_id,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if route == "research":
        return create_research_agent_graph(
            provider=provider,
            model=model,
            api_key=api_key,
            user_id=user_id,
            openai_api_key=openai_api_key,
            tavily_api_key=tavily_api_key,
            api_keys=api_keys,
            mcp_tools=mcp_tools,
            plugin_tools=plugin_tools,
            conversation_id=conversation_id,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if route == "writing":
        return create_writing_agent_graph(
            provider=provider,
            model=model,
            api_key=api_key,
            user_id=user_id,
            openai_api_key=openai_api_key,
            api_keys=api_keys,
            mcp_tools=mcp_tools,
            plugin_tools=plugin_tools,
            conversation_id=conversation_id,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    return create_graph(
        provider=provider,
        model=model,
        api_key=api_key,
        enabled_tools=enabled_tools,
        api_keys=api_keys,
        user_id=user_id,
        openai_api_key=openai_api_key,
        tavily_api_key=tavily_api_key,
        mcp_tools=mcp_tools,
        plugin_tools=plugin_tools,
        conversation_id=conversation_id,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )


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
