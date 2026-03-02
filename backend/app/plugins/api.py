"""PluginAPI — controlled interface exposed to each plugin during on_load."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from langchain_core.tools import BaseTool

if TYPE_CHECKING:
    from app.plugins.registry import PluginRegistry


class PluginAPI:
    """API surface a plugin receives in ``on_load``.

    Provides controlled, plugin-scoped access to JARVIS internals.
    """

    def __init__(self, *, plugin_id: str, registry: PluginRegistry) -> None:
        self._plugin_id = plugin_id
        self._registry = registry

    def register_tool(self, tool: BaseTool) -> None:
        """Register a LangChain tool contributed by this plugin."""
        self._registry.add_tool(self._plugin_id, tool)

    def register_channel(self, adapter: object) -> None:
        """Register a ChannelAdapter contributed by this plugin."""
        self._registry.add_channel(self._plugin_id, adapter)

    def get_config(self, key: str, default: str | None = None) -> str | None:
        """Read a configuration value from environment variables."""
        return os.environ.get(key, default)
