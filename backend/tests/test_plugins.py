"""Tests for the JARVIS Plugin SDK."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.plugins.api import PluginAPI
from app.plugins.registry import PluginRegistry
from app.plugins.sdk import JarvisPlugin


class _HelloPlugin(JarvisPlugin):
    """Test plugin for PluginRegistry tests."""

    plugin_id = "hello"
    plugin_name = "Hello Plugin"
    plugin_description = "Test plugin"

    def __init__(self) -> None:
        self.loaded = False
        self.unloaded = False

    async def on_load(self, api: PluginAPI) -> None:
        self.loaded = True

    async def on_unload(self) -> None:
        self.unloaded = True


def test_registry_register_and_list():
    reg = PluginRegistry()
    plugin = _HelloPlugin()
    reg.register_plugin(plugin)

    plugins = reg.list_plugins()
    assert len(plugins) == 1
    assert plugins[0]["id"] == "hello"
    assert plugins[0]["name"] == "Hello Plugin"


def test_registry_add_tool():
    reg = PluginRegistry()
    plugin = _HelloPlugin()
    reg.register_plugin(plugin)

    mock_tool = MagicMock()
    mock_tool.name = "my_tool"
    reg.add_tool("hello", mock_tool)

    assert len(reg.get_all_tools()) == 1
    assert reg.get_all_tools()[0].name == "my_tool"


def test_registry_add_channel():
    reg = PluginRegistry()
    plugin = _HelloPlugin()
    reg.register_plugin(plugin)

    mock_channel = MagicMock()
    mock_channel.channel_name = "my_channel"
    reg.add_channel("hello", mock_channel)

    channels = reg.get_all_channels()
    assert len(channels) == 1
    assert channels[0].channel_name == "my_channel"


def test_registry_unregister():
    reg = PluginRegistry()
    plugin = _HelloPlugin()
    reg.register_plugin(plugin)
    reg.unregister_plugin("hello")

    assert reg.list_plugins() == []


def test_registry_unknown_plugin_add_tool_noop():
    """Adding a tool for an unregistered plugin should not raise."""
    reg = PluginRegistry()
    mock_tool = MagicMock()
    reg.add_tool("nonexistent", mock_tool)  # should not raise
    assert reg.get_all_tools() == []


def test_registry_is_empty():
    reg = PluginRegistry()
    assert reg.is_empty
    reg.register_plugin(_HelloPlugin())
    assert not reg.is_empty


def test_registry_duplicate_id_skipped():
    """Registering a second plugin with the same plugin_id is silently dropped."""
    reg = PluginRegistry()
    reg.register_plugin(_HelloPlugin())
    reg.register_plugin(_HelloPlugin())  # duplicate — should not raise
    assert len(reg.list_plugins()) == 1


@pytest.mark.asyncio
async def test_instantiate_missing_plugin_id_is_evicted():
    """Plugins without plugin_id are caught during directory loading."""
    from app.plugins.loader import load_all_plugins

    plugin_src = """\
from app.plugins.sdk import JarvisPlugin
from app.plugins.api import PluginAPI


class NoIdPlugin(JarvisPlugin):
    # missing plugin_id and plugin_name
    async def on_load(self, api: PluginAPI) -> None:
        pass
"""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "no_id_plugin.py").write_text(plugin_src)
        reg = PluginRegistry()
        await load_all_plugins(reg, plugin_dirs=[Path(tmp)])
        assert reg.is_empty


def test_plugin_api_register_tool() -> None:
    reg = PluginRegistry()
    reg.register_plugin(_HelloPlugin())
    api = PluginAPI(plugin_id="hello", registry=reg)
    mock_tool = MagicMock()
    mock_tool.name = "api_tool"
    api.register_tool(mock_tool)
    assert len(reg.get_all_tools()) == 1


def test_plugin_api_get_config(monkeypatch: object) -> None:  # type: ignore[name-defined]
    reg = PluginRegistry()
    reg.register_plugin(_HelloPlugin())
    api = PluginAPI(plugin_id="hello", registry=reg)
    monkeypatch.setenv("MY_PLUGIN_KEY", "secret")  # type: ignore[attr-defined]
    assert api.get_config("MY_PLUGIN_KEY") == "secret"
    assert api.get_config("MISSING_KEY", "default") == "default"
    assert api.get_config("MISSING_KEY") is None


@pytest.mark.asyncio
async def test_activate_all_plugins():
    from app.plugins.loader import activate_all_plugins

    reg = PluginRegistry()
    plugin = _HelloPlugin()
    reg.register_plugin(plugin)

    await activate_all_plugins(reg)
    assert plugin.loaded is True


@pytest.mark.asyncio
async def test_deactivate_all_plugins():
    from app.plugins.loader import deactivate_all_plugins

    reg = PluginRegistry()
    plugin = _HelloPlugin()
    reg.register_plugin(plugin)

    await deactivate_all_plugins(reg)
    assert plugin.unloaded is True


@pytest.mark.asyncio
async def test_load_from_directory():
    """Plugins in a directory are discovered and registered."""
    from app.plugins.loader import load_all_plugins

    plugin_src = """\
from app.plugins.sdk import JarvisPlugin
from app.plugins.api import PluginAPI


class MyPlugin(JarvisPlugin):
    plugin_id = "dir_plugin"
    plugin_name = "Directory Plugin"

    async def on_load(self, api: PluginAPI) -> None:
        pass
"""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "my_plugin.py").write_text(plugin_src)
        reg = PluginRegistry()
        await load_all_plugins(reg, plugin_dirs=[Path(tmp)])
        ids = [p["id"] for p in reg.list_plugins()]
        assert "dir_plugin" in ids


@pytest.mark.asyncio
async def test_load_from_directory_missing_dir():
    """Non-existent plugin directory should not raise."""
    from app.plugins.loader import load_all_plugins

    reg = PluginRegistry()
    await load_all_plugins(reg, plugin_dirs=[Path("/nonexistent/path")])
    assert reg.is_empty


def test_load_from_directory_oserror(tmp_path: Path) -> None:
    """OSError on iterdir() is caught and logged; no exception propagates."""
    from app.plugins.loader import _load_from_directory

    reg = PluginRegistry()
    with patch.object(type(tmp_path), "iterdir", side_effect=OSError("no access")):
        _load_from_directory(reg, tmp_path)  # must not raise

    assert reg.is_empty


@pytest.mark.asyncio
async def test_activate_plugin_failure_removes_plugin() -> None:
    """Plugins that fail on_load are removed from the registry."""
    from app.plugins.loader import activate_all_plugins

    class _BadPlugin(JarvisPlugin):
        plugin_id = "bad"
        plugin_name = "Bad Plugin"

        async def on_load(self, api: PluginAPI) -> None:
            raise RuntimeError("intentional failure")

    reg = PluginRegistry()
    reg.register_plugin(_BadPlugin())
    await activate_all_plugins(reg)
    assert reg.is_empty


def test_failed_module_load_cleans_sys_modules(tmp_path: Path) -> None:
    """Failed exec_module should not leave ghost entry in sys.modules."""
    import sys

    from app.plugins.loader import _load_module_file

    bad_plugin = tmp_path / "bad_plugin.py"
    bad_plugin.write_text("raise RuntimeError('intentional')")
    reg = PluginRegistry()
    _load_module_file(bad_plugin, reg)
    assert "jarvis_user_plugins.bad_plugin" not in sys.modules
