"""Plugin registry — tracks loaded plugins and their contributions."""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog
from langchain_core.tools import BaseTool

from app.plugins.sdk import JarvisPlugin

logger = structlog.get_logger(__name__)


@dataclass
class _PluginEntry:
    plugin: JarvisPlugin
    tools: list[BaseTool] = field(default_factory=list)
    channels: list = field(default_factory=list)  # list[BaseChannelAdapter]


class PluginRegistry:
    """Central store for all discovered plugins and their contributions."""

    def __init__(self) -> None:
        self._entries: dict[str, _PluginEntry] = {}

    def register_plugin(self, plugin: JarvisPlugin) -> None:
        if plugin.plugin_id in self._entries:
            logger.warning("plugin_duplicate_id", plugin_id=plugin.plugin_id)
            return
        self._entries[plugin.plugin_id] = _PluginEntry(plugin=plugin)

    def iter_entries(self) -> list[tuple[str, _PluginEntry]]:
        """Return a snapshot of (plugin_id, entry) pairs for safe iteration."""
        return list(self._entries.items())

    def unregister_plugin(self, plugin_id: str) -> None:
        self._entries.pop(plugin_id, None)

    def add_tool(self, plugin_id: str, tool: BaseTool) -> None:
        if plugin_id in self._entries:
            self._entries[plugin_id].tools.append(tool)

    def add_channel(self, plugin_id: str, adapter: object) -> None:
        if plugin_id in self._entries:
            self._entries[plugin_id].channels.append(adapter)

    def get_all_tools(self) -> list[BaseTool]:
        tools: list[BaseTool] = []
        for entry in self._entries.values():
            tools.extend(entry.tools)
        return tools

    def get_all_channels(self) -> list:
        channels: list = []
        for entry in self._entries.values():
            channels.extend(entry.channels)
        return channels

    def list_plugins(self) -> list[dict]:
        """Return metadata for all registered plugins."""
        result: list[dict] = []
        for entry in self._entries.values():
            m = entry.plugin.manifest
            result.append(
                {
                    **m.model_dump(),
                    "tools": [t.name for t in entry.tools],
                    "channels": [
                        getattr(c, "channel_name", str(c)) for c in entry.channels
                    ],
                }
            )
        return result

    @property
    def is_empty(self) -> bool:
        return not self._entries
