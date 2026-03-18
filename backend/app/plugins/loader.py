"""Plugin & Skill loader — supports OpenClaw-style manifest.yaml skills."""

from __future__ import annotations

import asyncio
import importlib
import importlib.metadata
import importlib.util
import inspect
import io
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

import httpx
import structlog
import yaml

from app.core.config import settings
from app.plugins.api import PluginAPI
from app.plugins.registry import PluginRegistry
from app.plugins.sdk import (
    JarvisPlugin,
    JarvisPluginManifest,
    PluginCategory,
)

logger = structlog.get_logger(__name__)

_ENTRY_POINT_GROUP = "jarvis_plugins"
_DEFAULT_PLUGIN_DIR = Path.home() / ".jarvis" / "plugins"

# Protects system plugin reload against concurrent admin installs
_system_reload_lock = asyncio.Lock()


async def reload_system_plugins(registry: PluginRegistry) -> None:
    """Reload system plugins under a lock to prevent concurrent reload races."""
    async with _system_reload_lock:
        await deactivate_all_plugins(registry)
        registry._entries.clear()
        await load_all_plugins(registry)
        await activate_all_plugins(registry)


async def install_plugin_from_url(url: str, registry: PluginRegistry) -> str:
    """Download a plugin/skill from a URL (supports .py or .zip for packages)."""
    _DEFAULT_PLUGIN_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

        # Handle single .py file
        if url.endswith(".py"):
            filename = url.split("/")[-1]
            dest_path = _DEFAULT_PLUGIN_DIR / filename
            dest_path.write_text(response.text)
            _load_module_file(dest_path, registry)
            return filename.replace(".py", "")

        # Handle .zip (OpenClaw skill package)
        if url.endswith(".zip") or "archive" in url:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                # Extract to a unique directory under plugins
                pkg_name = (
                    url.split("/")[-1]
                    .replace(".zip", "")
                    .replace(".main", "")
                    .replace(".master", "")
                )
                extract_path = _DEFAULT_PLUGIN_DIR / pkg_name
                z.extractall(extract_path)

                # Check if nested (common in GitHub zips)
                nested_dirs = list(extract_path.glob("*/manifest.yaml"))
                if nested_dirs:
                    # Move content up
                    real_pkg_path = nested_dirs[0].parent
                    temp_path = _DEFAULT_PLUGIN_DIR / f"{pkg_name}_tmp"
                    shutil.copytree(real_pkg_path, temp_path)
                    shutil.rmtree(extract_path)
                    shutil.move(temp_path, extract_path)

                _load_plugin_package(extract_path, registry)
                return pkg_name

    return "unknown"


async def load_all_plugins(
    registry: PluginRegistry,
    plugin_dirs: list[Path] | None = None,
) -> None:
    """Discover plugins from entry points and directories."""
    _load_from_entry_points(registry)
    dirs = list(plugin_dirs or [])
    if _DEFAULT_PLUGIN_DIR not in dirs:
        dirs.append(_DEFAULT_PLUGIN_DIR)

    # Also search project-level skills/ and settings.skills_dir
    project_skills_dir = Path(__file__).parents[3] / "skills"
    config_skills_dir = Path(settings.skills_dir)

    for d in dirs:
        _load_from_directory(registry, d)

    # Load lightweight Markdown skills
    await load_markdown_skills(registry, [project_skills_dir, config_skills_dir])


async def load_markdown_skills(
    registry: PluginRegistry,
    skill_dirs: list[Path],
) -> None:
    """Scan directories for SKILL.md files and register them as tools."""
    from app.plugins.skill_parser import SkillParser
    from app.sandbox.manager import SandboxManager

    parser = SkillParser(sandbox_manager=SandboxManager())

    for directory in skill_dirs:
        if not directory.exists():
            continue

        # Recursive search for .md files
        for path in directory.rglob("*.md"):
            if path.name.startswith("_"):
                continue

            try:
                md_content = path.read_text(encoding="utf-8")
                # Basic check if it's a SKILL.md
                if "# " in md_content and (
                    "## Implementation" in md_content or "## Prompt" in md_content
                ):
                    skill_data = parser.parse_markdown(md_content, path.name)
                    tool = parser.create_tool(skill_data)

                    # For now, let's register it as a "virtual" plugin
                    class VirtualSkillPlugin(JarvisPlugin):
                        def __init__(self, tool: Any, data: dict[str, Any]) -> None:
                            self.tool = tool
                            self.manifest = JarvisPluginManifest(
                                plugin_id=f"skill_{tool.name}",
                                name=data["name"],
                                description=data["description"],
                                category=PluginCategory.TOOL,
                                version="0.1.0",
                            )

                        async def on_load(self, api: PluginAPI) -> None:
                            api.register_tool(self.tool)

                    virtual_plugin = VirtualSkillPlugin(tool, skill_data)
                    registry.register_plugin(virtual_plugin)
                    logger.info(
                        "skill_registered",
                        skill_name=skill_data["name"],
                        path=str(path),
                    )
            except Exception:
                logger.exception("skill_load_failed", path=str(path))


def _load_from_directory(registry: PluginRegistry, directory: Path) -> None:
    """Scan directory for .py files or OpenClaw-style packages."""
    if not directory.exists():
        return
    try:
        entries = sorted(directory.iterdir())
    except OSError:
        logger.exception("plugin_directory_scan_failed", directory=str(directory))
        return
    for path in entries:
        if path.name.startswith("_"):
            continue
        if path.suffix == ".py":
            _load_module_file(path, registry)
        elif path.is_dir():
            if (path / "manifest.yaml").exists() or (path / "manifest.yml").exists():
                _load_plugin_package(path, registry)
            elif (path / "__init__.py").exists():
                _load_module_file(path / "__init__.py", registry, module_name=path.name)


def _load_plugin_package(path: Path, registry: PluginRegistry) -> None:
    """Load a plugin from a directory containing manifest.yaml (OpenClaw style)."""
    manifest_path = path / "manifest.yaml"
    if not manifest_path.exists():
        manifest_path = path / "manifest.yml"

    try:
        with open(manifest_path) as f:
            data = yaml.safe_load(f)
            manifest = JarvisPluginManifest(**data)

        # Entry point is usually main.py in the package
        entry_file = path / data.get("entry_point", "main.py")
        if not entry_file.exists():
            logger.error("plugin_package_missing_entry", path=str(path))
            return

        _load_module_file(entry_file, registry, manifest_override=manifest)
    except Exception:
        logger.exception("plugin_package_load_failed", path=str(path))


def _load_module_file(
    path: Path,
    registry: PluginRegistry,
    module_name: str | None = None,
    manifest_override: JarvisPluginManifest | None = None,
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
        if obj.__module__ != namespaced:
            continue  # skip classes imported from other modules
        if issubclass(obj, JarvisPlugin) and obj is not JarvisPlugin:
            _instantiate_and_register(obj, registry, manifest_override)


def _instantiate_and_register(
    plugin_class: type,
    registry: PluginRegistry,
    manifest_override: JarvisPluginManifest | None = None,
) -> None:
    """Instantiate a plugin class and register it if valid."""
    try:
        plugin = plugin_class()
        if manifest_override:
            plugin.manifest = manifest_override

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


async def activate_all_plugins(registry: PluginRegistry) -> None:
    """Call ``on_load`` for every discovered plugin."""
    for plugin_id, entry in registry.iter_entries():
        api = PluginAPI(plugin_id=plugin_id, registry=registry)
        try:
            await entry.plugin.on_load(api)
            logger.info("plugin_activated", plugin_id=plugin_id)
        except Exception:
            logger.exception("plugin_activation_failed", plugin_id=plugin_id)
            registry.unregister_plugin(plugin_id)


async def deactivate_all_plugins(registry: PluginRegistry) -> None:
    """Call ``on_unload`` for every active plugin (best-effort)."""
    for plugin_id, entry in registry.iter_entries():
        try:
            await entry.plugin.on_unload()
        except Exception:
            logger.exception("plugin_unload_failed", plugin_id=plugin_id)


async def reload_plugins(registry: PluginRegistry) -> None:
    """Deactivate, reload and reactivate all plugins."""
    await deactivate_all_plugins(registry)
    # Clear registry except core? No, usually safer to just clear all and reload.
    # But registry might have core tools.
    # Let's see if we can just re-run load_all_plugins.
    await load_all_plugins(registry)
    await activate_all_plugins(registry)


def _load_from_entry_points(registry: PluginRegistry) -> None:
    """Load plugins registered via Python package entry points."""
    try:
        eps = importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP)
        for ep in eps:
            try:
                plugin_class = ep.load()
                _instantiate_and_register(plugin_class, registry)
            except Exception:
                logger.exception("plugin_entry_point_load_failed", entry_point=ep.name)
    except Exception:
        return
