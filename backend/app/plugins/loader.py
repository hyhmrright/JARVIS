"""Plugin loader — discovers and activates plugins."""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import inspect
import sys
from pathlib import Path

import httpx
import structlog

from app.plugins.api import PluginAPI
from app.plugins.registry import PluginRegistry
from app.plugins.sdk import JarvisPlugin

logger = structlog.get_logger(__name__)

_ENTRY_POINT_GROUP = "jarvis_plugins"
_DEFAULT_PLUGIN_DIR = Path.home() / ".jarvis" / "plugins"


async def install_plugin_from_url(url: str, registry: PluginRegistry) -> str:
    """Download a .py plugin file from a URL and load it immediately."""
    _DEFAULT_PLUGIN_DIR.mkdir(parents=True, exist_ok=True)

    filename = url.split("/")[-1]
    if not filename.endswith(".py"):
        filename += ".py"

    dest_path = _DEFAULT_PLUGIN_DIR / filename

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        dest_path.write_text(response.text)

    # Load into registry
    _load_module_file(dest_path, registry)

    return filename.replace(".py", "")


async def load_all_plugins(
    registry: PluginRegistry,
    plugin_dirs: list[Path] | None = None,
) -> None:
    """Discover plugins from entry points and directories.

    Plugins are added to the registry but ``on_load`` is not yet called.
    Call :func:`activate_all_plugins` afterwards.

    Args:
        registry: The plugin registry to populate.
        plugin_dirs: Extra directories to scan. The default ~/.jarvis/plugins/
            directory is always scanned in addition to any provided dirs.
    """
    _load_from_entry_points(registry)
    dirs = list(plugin_dirs or [])
    if _DEFAULT_PLUGIN_DIR not in dirs:
        dirs.append(_DEFAULT_PLUGIN_DIR)
    for d in dirs:
        _load_from_directory(registry, d)


async def activate_all_plugins(registry: PluginRegistry) -> None:
    """Call ``on_load`` for every discovered plugin.

    Plugins that raise during ``on_load`` are evicted from the registry.
    """
    for plugin_id, entry in registry.iter_entries():
        api = PluginAPI(plugin_id=plugin_id, registry=registry)
        try:
            await entry.plugin.on_load(api)
            logger.info("plugin_loaded", plugin_id=plugin_id)
        except Exception:
            logger.exception("plugin_load_failed", plugin_id=plugin_id)
            registry.unregister_plugin(plugin_id)


async def deactivate_all_plugins(registry: PluginRegistry) -> None:
    """Call ``on_unload`` for every active plugin (best-effort)."""
    for plugin_id, entry in registry.iter_entries():
        try:
            await entry.plugin.on_unload()
            logger.info("plugin_unloaded", plugin_id=plugin_id)
        except Exception:
            logger.exception("plugin_unload_failed", plugin_id=plugin_id)


def _load_from_entry_points(registry: PluginRegistry) -> None:
    """Load plugins registered via Python package entry points."""
    try:
        eps = importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP)
    except Exception:
        return
    for ep in eps:
        try:
            plugin_class = ep.load()
            _instantiate_and_register(plugin_class, registry)
        except Exception:
            logger.exception("plugin_entry_point_load_failed", entry_point=ep.name)


def _load_from_directory(registry: PluginRegistry, directory: Path) -> None:
    """Load plugins from ``.py`` files or packages in a directory."""
    if not directory.exists():
        return
    try:
        entries = sorted(directory.iterdir())
    except OSError:
        logger.exception("plugin_dir_scan_failed", directory=str(directory))
        return
    for path in entries:
        if path.suffix == ".py" and not path.name.startswith("_"):
            _load_module_file(path, registry)
        elif path.is_dir() and (path / "__init__.py").exists():
            _load_module_file(path / "__init__.py", registry, module_name=path.name)


def _load_module_file(
    path: Path,
    registry: PluginRegistry,
    module_name: str | None = None,
) -> None:
    name = module_name or path.stem
    namespaced = f"jarvis_user_plugins.{name}"
    spec = importlib.util.spec_from_file_location(namespaced, path)
    if spec is None or spec.loader is None:
        return
    try:
        module = importlib.util.module_from_spec(spec)
        sys.modules[namespaced] = module
        spec.loader.exec_module(module)
    except Exception:
        logger.exception("plugin_module_load_failed", path=str(path))
        sys.modules.pop(namespaced, None)  # 清理残留项
        return
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, JarvisPlugin) and obj is not JarvisPlugin:
            _instantiate_and_register(obj, registry)


def _instantiate_and_register(plugin_class: type, registry: PluginRegistry) -> None:
    """Instantiate a plugin class and register it if valid."""
    try:
        plugin = plugin_class()
        _validate_plugin(plugin, plugin_class)
        registry.register_plugin(plugin)
        logger.info(
            "plugin_discovered",
            plugin_id=plugin.plugin_id,
            name=plugin.manifest.name,
        )
    except Exception:
        logger.exception("plugin_instantiation_failed", cls=plugin_class.__name__)


def _validate_plugin(plugin: JarvisPlugin, plugin_class: type) -> None:
    """Validate that plugin has a valid manifest."""
    if not hasattr(plugin, "manifest") or plugin.manifest is None:
        raise TypeError(f"{plugin_class.__name__} must define 'manifest'")

    from app.plugins.sdk import JarvisPluginManifest

    if not isinstance(plugin.manifest, JarvisPluginManifest):
        raise TypeError(
            f"{plugin_class.__name__}.manifest must be a JarvisPluginManifest instance"
        )
