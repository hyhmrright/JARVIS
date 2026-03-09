"""Tests for the gateway layer: models, registry, session manager, and router."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.gateway.channel_registry import ChannelRegistry
from app.channels.base import BaseChannelAdapter, GatewayMessage, chunk_text
from app.gateway.router import GatewayRouter
from app.gateway.session_manager import SessionManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeAdapter(BaseChannelAdapter):
    channel_name = "fake"

    def __init__(self) -> None:
        super().__init__()
        self.started = False
        self.stopped = False
        self.sent: list[tuple[str, str]] = []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        self.sent.append((channel_id, content))


def _make_redis_mock(stored: dict | None = None) -> MagicMock:
    """Return an async-capable Redis mock backed by an in-memory dict."""
    store: dict[str, bytes] = {}
    if stored:
        store.update({k: json.dumps(v).encode() for k, v in stored.items()})

    redis = MagicMock()

    async def _get(key: str) -> bytes | None:
        return store.get(key)

    async def _setex(key: str, ttl: int, value: str) -> None:
        store[key] = value.encode() if isinstance(value, str) else value

    async def _delete(key: str) -> None:
        store.pop(key, None)

    redis.get = AsyncMock(side_effect=_get)
    redis.setex = AsyncMock(side_effect=_setex)
    redis.delete = AsyncMock(side_effect=_delete)
    return redis


# ---------------------------------------------------------------------------
# GatewayMessage tests
# ---------------------------------------------------------------------------


def test_gateway_message_defaults() -> None:
    """GatewayMessage should populate defaults for attachments and metadata."""
    msg = GatewayMessage(
        sender_id="u1",
        channel="telegram",
        channel_id="chat_123",
        content="hello",
    )
    assert msg.attachments == []
    assert msg.metadata == {}


def test_gateway_message_custom_fields() -> None:
    """GatewayMessage should store all provided fields correctly."""
    msg = GatewayMessage(
        sender_id="u1",
        channel="discord",
        channel_id="chan_456",
        content="hi",
        attachments=["file.png"],
        metadata={"reply_to": 99},
    )
    assert msg.channel == "discord"
    assert msg.attachments == ["file.png"]
    assert msg.metadata["reply_to"] == 99


# ---------------------------------------------------------------------------
# chunk_text tests
# ---------------------------------------------------------------------------


def test_chunk_text_short_string() -> None:
    assert chunk_text("hello", 10) == ["hello"]


def test_chunk_text_exact_limit() -> None:
    assert chunk_text("abcde", 5) == ["abcde"]


def test_chunk_text_long_string() -> None:
    result = chunk_text("abcdefghij", 3)
    assert result == ["abc", "def", "ghi", "j"]


def test_chunk_text_empty_string() -> None:
    assert chunk_text("", 10) == []


# ---------------------------------------------------------------------------
# ChannelAdapter tests
# ---------------------------------------------------------------------------


def test_channel_adapter_set_message_handler() -> None:
    """set_message_handler should store the handler on the adapter."""

    async def _handler(msg: GatewayMessage) -> None:
        pass

    adapter = _FakeAdapter()
    adapter.set_message_handler(_handler)
    assert adapter._message_handler is _handler


# ---------------------------------------------------------------------------
# ChannelRegistry tests
# ---------------------------------------------------------------------------


def test_registry_register_and_get() -> None:
    """Registered adapter should be retrievable by channel name."""
    registry = ChannelRegistry()
    adapter = _FakeAdapter()
    registry.register(adapter)
    assert registry.get("fake") is adapter


def test_registry_get_unknown_returns_none() -> None:
    """get() for an unknown channel should return None."""
    registry = ChannelRegistry()
    assert registry.get("nonexistent") is None


def test_registry_all_channels() -> None:
    """all_channels() should list every registered channel name."""
    registry = ChannelRegistry()
    registry.register(_FakeAdapter())
    assert "fake" in registry.all_channels()


@pytest.mark.asyncio
async def test_registry_start_all() -> None:
    """start_all() should call start() on every adapter."""
    registry = ChannelRegistry()
    adapter = _FakeAdapter()
    registry.register(adapter)
    await registry.start_all()
    assert adapter.started is True


@pytest.mark.asyncio
async def test_registry_stop_all() -> None:
    """stop_all() should call stop() on every adapter."""
    registry = ChannelRegistry()
    adapter = _FakeAdapter()
    registry.register(adapter)
    await registry.stop_all()
    assert adapter.stopped is True


# ---------------------------------------------------------------------------
# SessionManager tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_manager_creates_session() -> None:
    """get_or_create_session should create a new session when none exists."""
    redis = _make_redis_mock()
    manager = SessionManager(redis)
    session = await manager.get_or_create_session("alice", "telegram")
    assert session["sender_id"] == "alice"
    assert session["channel"] == "telegram"
    assert session["user_id"] is None


@pytest.mark.asyncio
async def test_session_manager_returns_existing_session() -> None:
    """get_or_create_session should return the stored session on second call."""
    redis = _make_redis_mock()
    manager = SessionManager(redis)
    first = await manager.get_or_create_session("bob", "discord")
    second = await manager.get_or_create_session("bob", "discord")
    assert first == second


@pytest.mark.asyncio
async def test_session_manager_link_user() -> None:
    """link_user should persist the user_id in the session."""
    redis = _make_redis_mock()
    manager = SessionManager(redis)
    await manager.get_or_create_session("carol", "telegram")
    await manager.link_user("carol", "telegram", "user-uuid-123")
    session = await manager.get_or_create_session("carol", "telegram")
    assert session["user_id"] == "user-uuid-123"


@pytest.mark.asyncio
async def test_session_manager_delete_session() -> None:
    """delete_session should remove the session so a fresh one is created next time."""
    redis = _make_redis_mock()
    manager = SessionManager(redis)
    await manager.get_or_create_session("dave", "telegram")
    await manager.link_user("dave", "telegram", "user-uuid-999")
    await manager.delete_session("dave", "telegram")
    # After deletion a brand-new session (user_id=None) should be returned
    fresh = await manager.get_or_create_session("dave", "telegram")
    assert fresh["user_id"] is None


# ---------------------------------------------------------------------------
# GatewayRouter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_unknown_channel_raises() -> None:
    """handle_message with an unregistered channel should raise ValueError."""
    registry = ChannelRegistry()
    manager = SessionManager(_make_redis_mock())
    router = GatewayRouter(registry, manager)
    msg = GatewayMessage(
        sender_id="u1", channel="unknown", channel_id="c1", content="hi"
    )
    with pytest.raises(ValueError, match="Unknown channel"):
        await router.handle_message(msg)


@pytest.mark.asyncio
async def test_router_unauthenticated_returns_pairing_prompt() -> None:
    """handle_message without a linked user should return the pairing prompt."""
    from app.gateway.security import PAIRING_PROMPT

    registry = ChannelRegistry()
    registry.register(_FakeAdapter())
    manager = SessionManager(_make_redis_mock())
    router = GatewayRouter(registry, manager)
    msg = GatewayMessage(sender_id="u1", channel="fake", channel_id="c1", content="hi")
    reply = await router.handle_message(msg)
    assert reply == PAIRING_PROMPT


@pytest.mark.asyncio
async def test_router_dispatches_to_agent() -> None:
    """handle_message should call _run_agent and return its reply."""
    registry = ChannelRegistry()
    registry.register(_FakeAdapter())
    redis = _make_redis_mock()
    manager = SessionManager(redis)
    await manager.get_or_create_session("u1", "fake")
    await manager.link_user("u1", "fake", "jarvis-user-1")

    router = GatewayRouter(registry, manager)

    # Patch _run_agent to avoid requiring LangGraph infrastructure
    async def _fake_agent(user_id: str, message: GatewayMessage, **_kw: object) -> str:
        return f"Hello from agent, {user_id}"

    router._run_agent = _fake_agent  # type: ignore[method-assign]

    msg = GatewayMessage(
        sender_id="u1", channel="fake", channel_id="c1", content="ping"
    )
    reply = await router.handle_message(msg)
    assert reply == "Hello from agent, jarvis-user-1"
