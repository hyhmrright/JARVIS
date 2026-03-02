"""JARVIS Plugin SDK — base class for all plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.plugins.api import PluginAPI


class JarvisPlugin(ABC):
    """Base class for all JARVIS plugins.

    Subclasses must set class-level ``plugin_id`` and ``plugin_name``,
    and implement ``on_load``.  A minimal plugin looks like::

        class MyPlugin(JarvisPlugin):
            plugin_id = "my-plugin"
            plugin_name = "My Plugin"

            async def on_load(self, api: PluginAPI) -> None:
                api.register_tool(my_langchain_tool)
    """

    plugin_id: str  # unique identifier, set on subclass
    plugin_name: str  # human-readable name, set on subclass
    plugin_version: str = "0.1.0"
    plugin_description: str = ""

    @abstractmethod
    async def on_load(self, api: PluginAPI) -> None:
        """Called once when the plugin is activated.

        Use *api* to register tools, channels, and read configuration.
        Raising an exception here causes the plugin to be evicted.
        """

    async def on_unload(self) -> None:  # noqa: B027
        """Called once when the plugin is deactivated (app shutdown)."""
