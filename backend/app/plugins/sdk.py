"""JARVIS Plugin SDK — base class for all plugins."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.plugins.api import PluginAPI


class PluginCategory(enum.StrEnum):
    TOOL = "tool"
    CHANNEL = "channel"
    RAG = "rag"
    AUTOMATION = "automation"
    UI = "ui"
    SYSTEM = "system"


class JarvisPluginManifest(BaseModel):
    """Declarative metadata for a JARVIS plugin (inspired by OpenClaw)."""

    plugin_id: str = Field(..., description="Unique slug for the plugin")
    name: str = Field(..., description="Human-readable name")
    version: str = Field("0.1.0", description="Semver version string")
    description: str = Field("", description="Brief purpose of the plugin")
    category: PluginCategory = Field(PluginCategory.TOOL)
    author: str | None = None
    homepage: str | None = None
    license: str | None = "MIT"
    requires: list[str] = Field(
        default_factory=list, description="IDs of dependency plugins"
    )
    config_schema: dict[str, Any] | None = Field(
        None, description="JSON Schema for plugin-specific configuration"
    )


class JarvisPlugin(ABC):
    """Base class for all JARVIS plugins.

    Subclasses must set class-level ``manifest`` and implement ``on_load``.
    A minimal plugin looks like::

        class MyPlugin(JarvisPlugin):
            manifest = JarvisPluginManifest(
                plugin_id="my-plugin",
                name="My Plugin",
                description="Example plugin"
            )

            async def on_load(self, api: PluginAPI) -> None:
                api.register_tool(my_langchain_tool)
    """

    manifest: JarvisPluginManifest

    @property
    def plugin_id(self) -> str:
        return self.manifest.plugin_id

    @property
    def plugin_name(self) -> str:
        return self.manifest.name

    @abstractmethod
    async def on_load(self, api: PluginAPI) -> None:
        """Called once when the plugin is activated.

        Use *api* to register tools, channels, and read configuration.
        Raising an exception here causes the plugin to be evicted.
        """

    async def on_unload(self) -> None:  # noqa: B027
        """Called once when the plugin is deactivated (app shutdown)."""


class SimpleSkillPlugin(JarvisPlugin):
    """A plugin that automatically registers its methods as tools (OpenClaw style).

    Subclasses should define manifest and methods with docstrings.
    """

    async def on_load(self, api: PluginAPI) -> None:
        from langchain_core.tools import StructuredTool

        # Automatically discover and register methods as tools
        for name in dir(self):
            if name.startswith("_") or name in (
                "on_load",
                "on_unload",
                "plugin_id",
                "plugin_name",
                "manifest",
            ):
                continue

            member = getattr(self, name)
            if not callable(member):
                continue

            # Use method docstring as tool description
            doc = member.__doc__ or f"Execute {name} task."

            tool = StructuredTool.from_function(
                func=member,
                name=f"{self.plugin_id}_{name}",
                description=doc,
            )
            api.register_tool(tool)
