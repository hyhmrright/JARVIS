"""Unit tests for chat.py helper functions: _load_tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.chat import _load_tools

# MCP tools are lazy-imported inside _load_tools, so patch at source module
_MCP_CREATE = "app.tools.mcp_client.create_mcp_tools"
_MCP_PARSE = "app.tools.mcp_client.parse_mcp_configs"
_PLUGIN_REGISTRY = "app.api.chat.plugin_registry"


# ---------------------------------------------------------------------------
# _load_tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_tools_both_when_enabled_tools_is_none():
    """enabled_tools=None loads both MCP and plugin tools."""
    fake_mcp = [MagicMock()]
    fake_plugins = [MagicMock()]

    with (
        patch(_MCP_CREATE, new_callable=AsyncMock, return_value=fake_mcp),
        patch(_MCP_PARSE, return_value=[]),
        patch(_PLUGIN_REGISTRY) as mock_registry,
    ):
        mock_registry.get_all_tools.return_value = fake_plugins
        mcp_tools, plugin_tools = await _load_tools(None)

    assert mcp_tools == fake_mcp
    assert plugin_tools == fake_plugins


@pytest.mark.asyncio
async def test_load_tools_mcp_only_skips_plugin():
    """enabled_tools=['mcp'] loads MCP but returns plugin_tools=None."""
    fake_mcp = [MagicMock()]

    with (
        patch(_MCP_CREATE, new_callable=AsyncMock, return_value=fake_mcp),
        patch(_MCP_PARSE, return_value=[]),
        patch(_PLUGIN_REGISTRY) as mock_registry,
    ):
        mcp_tools, plugin_tools = await _load_tools(["mcp"])

    assert mcp_tools == fake_mcp
    assert plugin_tools is None
    mock_registry.get_all_tools.assert_not_called()


@pytest.mark.asyncio
async def test_load_tools_plugin_only_skips_mcp():
    """enabled_tools=['plugin'] skips MCP and loads plugin tools."""
    fake_plugins = [MagicMock()]

    # No MCP patches: the MCP branch is never entered so importing mcp_client
    # should not be required (avoids fragility when optional deps are absent).
    with patch(_PLUGIN_REGISTRY) as mock_registry:
        mock_registry.get_all_tools.return_value = fake_plugins
        mcp_tools, plugin_tools = await _load_tools(["plugin"])

    assert mcp_tools == []
    assert plugin_tools == fake_plugins


@pytest.mark.asyncio
async def test_load_tools_neither_when_no_relevant_tool():
    """enabled_tools=['datetime'] loads neither MCP nor plugin tools."""
    with patch(_PLUGIN_REGISTRY) as mock_registry:
        mcp_tools, plugin_tools = await _load_tools(["datetime"])

    assert mcp_tools == []
    assert plugin_tools is None
    mock_registry.get_all_tools.assert_not_called()
