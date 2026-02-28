"""Tests for gateway → agent wiring (GatewayRouter._run_agent)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.gateway.channel_registry import ChannelRegistry
from app.gateway.models import GatewayMessage
from app.gateway.router import GatewayRouter
from app.gateway.session_manager import SessionManager


def _make_router(
    session_mgr: SessionManager,
    *,
    db_session_factory: type | None = None,
) -> GatewayRouter:
    registry = ChannelRegistry()
    adapter = MagicMock()
    adapter.channel_name = "test"
    registry.register(adapter)
    return GatewayRouter(registry, session_mgr, db_session_factory=db_session_factory)


@pytest.mark.asyncio
async def test_run_agent_creates_conversation_and_returns_reply():
    """_run_agent should create conversation, invoke graph, persist messages."""
    # Mock DB session
    mock_user_settings = MagicMock()
    mock_user_settings.model_provider = "deepseek"
    mock_user_settings.model_name = "deepseek-chat"
    mock_user_settings.api_keys = {}
    mock_user_settings.enabled_tools = ["datetime"]
    mock_user_settings.persona_override = None

    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=mock_user_settings)
    mock_db.get = AsyncMock(return_value=None)  # No existing conversation
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    mock_db.scalars = AsyncMock(return_value=scalars_result)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_factory.return_value = mock_ctx

    # Mock session manager
    mock_session_mgr = AsyncMock(spec=SessionManager)
    mock_session_mgr.get_or_create_session.return_value = {
        "sender_id": "u1",
        "channel": "test",
        "user_id": "00000000-0000-0000-0000-000000000001",
    }

    # Mock graph
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "messages": [AIMessage(content="Hello from JARVIS!")]
    }

    router = _make_router(mock_session_mgr, db_session_factory=mock_factory)

    with (
        patch(
            "app.gateway.router.resolve_api_keys",
            return_value=["fake-key"],
        ),
        patch("app.gateway.router.create_graph", return_value=mock_graph),
    ):
        msg = GatewayMessage(
            sender_id="u1", channel="test", channel_id="ch1", content="Hello"
        )
        reply = await router._run_agent(
            user_id="00000000-0000-0000-0000-000000000001",
            message=msg,
        )

    assert reply == "Hello from JARVIS!"
    mock_graph.ainvoke.assert_called_once()
    # Two messages persisted: human + ai
    assert mock_db.add.call_count >= 2


@pytest.mark.asyncio
async def test_run_agent_no_api_key_returns_error():
    """When no API key is available, return an error message."""
    mock_user_settings = MagicMock()
    mock_user_settings.model_provider = "deepseek"
    mock_user_settings.model_name = "deepseek-chat"
    mock_user_settings.api_keys = {}
    mock_user_settings.enabled_tools = None
    mock_user_settings.persona_override = None

    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=mock_user_settings)

    mock_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_factory.return_value = mock_ctx

    mock_session_mgr = AsyncMock(spec=SessionManager)

    router = _make_router(mock_session_mgr, db_session_factory=mock_factory)

    with patch("app.gateway.router.resolve_api_keys", return_value=[]):
        msg = GatewayMessage(
            sender_id="u1", channel="test", channel_id="ch1", content="Hello"
        )
        reply = await router._run_agent(
            user_id="00000000-0000-0000-0000-000000000001",
            message=msg,
        )

    assert "No API key" in reply
