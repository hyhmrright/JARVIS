"""Unit tests for chat.py helper functions: _load_tools and _save_response."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.chat import _load_tools, _save_response

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


# ---------------------------------------------------------------------------
# _save_response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_response_empty_content_is_noop():
    """Empty full_content skips DB write entirely."""
    mock_llm = MagicMock()

    with patch("app.api.chat.AsyncSessionLocal") as mock_session_cls:
        await _save_response(uuid.uuid4(), "", None, mock_llm)

    mock_session_cls.assert_not_called()


@pytest.mark.asyncio
async def test_save_response_writes_message_to_db():
    """Non-empty full_content writes an AI Message to the DB."""
    mock_llm = MagicMock()
    mock_llm.provider = "deepseek"
    mock_llm.model_name = "deepseek-chat"

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    mock_begin_ctx = AsyncMock()
    mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
    mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = MagicMock(return_value=mock_begin_ctx)

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.api.chat.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.api.chat.sync_conversation_to_markdown") as mock_sync,
    ):
        await _save_response(uuid.uuid4(), "hello", None, mock_llm)

    mock_session.add.assert_called_once()
    mock_sync.assert_called_once()


@pytest.mark.asyncio
async def test_save_response_db_exception_is_swallowed():
    """DB failure does not propagate — _save_response always returns normally."""
    mock_llm = MagicMock()
    mock_llm.provider = "deepseek"
    mock_llm.model_name = "deepseek-chat"

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("app.api.chat.AsyncSessionLocal", return_value=mock_session_ctx):
        # Must not raise
        await _save_response(uuid.uuid4(), "hello", None, mock_llm)
