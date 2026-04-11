"""Agent tool management service.

Consolidates system tools, MCP tools, and personal plugins
loading logic into a single registry/loader.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from langchain_core.tools import BaseTool
from sqlalchemy import select

from app.core.config import settings
from app.db.models import InstalledPlugin
from app.plugins import plugin_registry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class ToolService:
    """Orchestrates loading and resolving agent tools."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def load_all_tools(
        self,
        user_id: str,
        enabled_tools: list[str] | None,
    ) -> tuple[list[BaseTool], list[BaseTool]]:
        """Load and return all tools (MCP and Plugins) allowed for this user."""
        (mcp_tools, plugin_tools), personal_tools = await asyncio.gather(
            self._load_standard_tools(enabled_tools),
            self._load_personal_plugins(user_id, enabled_tools),
        )
        if personal_tools:
            plugin_tools = [*(plugin_tools or []), *personal_tools]
        return mcp_tools, plugin_tools

    async def _load_standard_tools(
        self,
        enabled_tools: list[str] | None,
    ) -> tuple[list[BaseTool], list[BaseTool]]:
        mcp_tools: list[BaseTool] = []
        if enabled_tools is None or "mcp" in enabled_tools:
            from app.tools.mcp_client import create_mcp_tools, parse_mcp_configs

            mcp_tools = await create_mcp_tools(
                parse_mcp_configs(settings.mcp_servers_json)
            )

        plugin_tools: list[BaseTool] = []
        if enabled_tools is None or "plugin" in enabled_tools:
            plugin_tools = plugin_registry.get_all_tools() or []

        return mcp_tools, plugin_tools

    async def _load_personal_plugins(
        self,
        user_id: str,
        enabled_tools: list[str] | None,
    ) -> list[BaseTool]:
        if enabled_tools is not None and "plugin" not in enabled_tools:
            return []

        try:
            from app.plugins.loader import _load_from_directory, load_markdown_skills
            from app.plugins.registry import PluginRegistry

            personal_dir = Path(settings.installed_plugins_dir) / "users" / str(user_id)
            if not personal_dir.exists():
                return []

            result = await self._db.execute(
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
