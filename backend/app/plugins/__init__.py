"""JARVIS Plugin System."""

from app.plugins.registry import PluginRegistry

# Application-wide singleton — populated during lifespan startup.
plugin_registry = PluginRegistry()
