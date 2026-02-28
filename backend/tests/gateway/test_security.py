"""Tests for gateway pairing code security and router pairing integration."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.gateway.channel_registry import ChannelRegistry
from app.gateway.models import ChannelAdapter, GatewayMessage
from app.gateway.router import GatewayRouter
from app.gateway.security import (
    PAIRING_INVALID,
    PAIRING_PREFIX,
    PAIRING_PROMPT,
    PAIRING_SUCCESS,
    PairingManager,
)
from app.gateway.session_manager import SessionManager

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_redis_mock() -> MagicMock:
    """Return an async-capable Redis mock backed by an in-memory dict."""
    store: dict[str, bytes] = {}
    redis = MagicMock()

    async def _set(key: str, value: str | bytes, ex: int | None = None) -> None:
        store[key] = value.encode() if isinstance(value, str) else value

    async def _get(key: str) -> bytes | None:
        return store.get(key)

    async def _delete(*keys: str) -> int:
        deleted = sum(1 for k in keys if store.pop(k, None) is not None)
        return deleted

    async def _getdel(key: str) -> bytes | None:
        return store.pop(key, None)

    redis.set = AsyncMock(side_effect=_set)
    redis.get = AsyncMock(side_effect=_get)
    redis.getdel = AsyncMock(side_effect=_getdel)
    redis.delete = AsyncMock(side_effect=_delete)
    return redis


def _make_session_redis_mock(stored: dict | None = None) -> MagicMock:
    """Redis mock that also supports setex (used by SessionManager)."""
    store: dict[str, bytes] = {}
    if stored:
        store.update({k: json.dumps(v).encode() for k, v in stored.items()})
    redis = MagicMock()

    async def _get(key: str) -> bytes | None:
        return store.get(key)

    async def _setex(key: str, ttl: int, value: str) -> None:
        store[key] = value.encode() if isinstance(value, str) else value

    async def _delete(*keys: str) -> int:
        deleted = sum(1 for k in keys if store.pop(k, None) is not None)
        return deleted

    redis.get = AsyncMock(side_effect=_get)
    redis.setex = AsyncMock(side_effect=_setex)
    redis.delete = AsyncMock(side_effect=_delete)
    return redis


class _FakeAdapter(ChannelAdapter):
    channel_name = "fake"

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[str, str]] = []

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        self.sent.append((channel_id, content))


def _make_router_parts(
    *,
    include_pairing: bool = True,
) -> tuple[GatewayRouter, SessionManager, PairingManager | None]:
    """Build a GatewayRouter with a fake adapter and in-memory Redis mocks.

    Returns ``(router, session_manager, pairing_manager)`` so tests that need
    to inspect or interact with the session/pairing state can do so.
    """
    registry = ChannelRegistry()
    registry.register(_FakeAdapter())
    session_manager = SessionManager(_make_session_redis_mock())
    pairing_manager = PairingManager(_make_redis_mock()) if include_pairing else None
    router = GatewayRouter(registry, session_manager, pairing_manager)
    return router, session_manager, pairing_manager


# ---------------------------------------------------------------------------
# PairingManager — generate_code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_code_returns_six_digits() -> None:
    """generate_code should return a zero-padded 6-digit string."""
    redis = _make_redis_mock()
    manager = PairingManager(redis)
    code = await manager.generate_code("user-abc")
    assert len(code) == 6
    assert code.isdigit()


@pytest.mark.asyncio
async def test_generate_code_stores_user_id_in_redis() -> None:
    """generate_code should persist the user_id under the pairing key."""
    redis = _make_redis_mock()
    manager = PairingManager(redis)
    code = await manager.generate_code("user-xyz")
    key = f"{PAIRING_PREFIX}{code}"
    raw = await redis.get(key)
    assert raw is not None
    stored_user_id = raw if isinstance(raw, str) else raw.decode()
    assert stored_user_id == "user-xyz"


@pytest.mark.asyncio
async def test_generate_code_uses_ttl() -> None:
    """generate_code should call redis.set with an expiry (ex kwarg)."""
    redis = _make_redis_mock()
    manager = PairingManager(redis)
    await manager.generate_code("user-ttl")
    redis.set.assert_called_once()
    _, kwargs = redis.set.call_args
    assert kwargs["ex"] == 900


# ---------------------------------------------------------------------------
# PairingManager — validate_code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_code_returns_user_id_on_valid_code() -> None:
    """validate_code should return the user_id for a valid, unexpired code."""
    redis = _make_redis_mock()
    manager = PairingManager(redis)
    code = await manager.generate_code("user-valid")
    result = await manager.validate_code(code)
    assert result == "user-valid"


@pytest.mark.asyncio
async def test_validate_code_consumes_code() -> None:
    """validate_code should delete the code so it cannot be reused."""
    redis = _make_redis_mock()
    manager = PairingManager(redis)
    code = await manager.generate_code("user-consume")
    await manager.validate_code(code)
    # Second attempt should fail
    second = await manager.validate_code(code)
    assert second is None


@pytest.mark.asyncio
async def test_validate_code_returns_none_for_wrong_code() -> None:
    """validate_code should return None for a code that was never generated."""
    redis = _make_redis_mock()
    manager = PairingManager(redis)
    result = await manager.validate_code("000000")
    assert result is None


@pytest.mark.asyncio
async def test_validate_code_returns_none_for_expired_code() -> None:
    """validate_code should return None when the key is absent (simulates expiry)."""
    redis = _make_redis_mock()
    manager = PairingManager(redis)
    # Simulate expiry by never storing the key in Redis (nothing in the mock store)
    result = await manager.validate_code("123456")
    assert result is None


@pytest.mark.asyncio
async def test_validate_code_handles_bytes_value() -> None:
    """validate_code should decode bytes-type values returned by Redis."""
    redis = _make_redis_mock()
    # Manually inject a bytes value into the mock store
    await redis.set(f"{PAIRING_PREFIX}999999", b"user-bytes")
    manager = PairingManager(redis)
    result = await manager.validate_code("999999")
    assert result == "user-bytes"


# ---------------------------------------------------------------------------
# PairingManager — revoke_code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_code_returns_true_for_existing_code() -> None:
    """revoke_code should return True when the code existed."""
    redis = _make_redis_mock()
    manager = PairingManager(redis)
    code = await manager.generate_code("user-revoke")
    result = await manager.revoke_code(code)
    assert result is True


@pytest.mark.asyncio
async def test_revoke_code_returns_false_for_missing_code() -> None:
    """revoke_code should return False for a code that doesn't exist."""
    redis = _make_redis_mock()
    manager = PairingManager(redis)
    result = await manager.revoke_code("000000")
    assert result is False


@pytest.mark.asyncio
async def test_revoke_code_prevents_subsequent_validation() -> None:
    """A revoked code should fail validation."""
    redis = _make_redis_mock()
    manager = PairingManager(redis)
    code = await manager.generate_code("user-rev2")
    await manager.revoke_code(code)
    result = await manager.validate_code(code)
    assert result is None


# ---------------------------------------------------------------------------
# GatewayRouter — unauthenticated pairing flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_unauthenticated_non_code_returns_prompt() -> None:
    """Unauthenticated sender sending normal text should receive the pairing prompt."""
    router, _, _ = _make_router_parts()

    msg = GatewayMessage(
        sender_id="stranger", channel="fake", channel_id="c1", content="hello there"
    )
    reply = await router.handle_message(msg)
    assert reply == PAIRING_PROMPT


@pytest.mark.asyncio
async def test_router_unauthenticated_valid_code_links_account() -> None:
    """An unauthenticated sender sending a valid code should get a success message."""
    router, session_manager, pairing_manager = _make_router_parts()
    assert pairing_manager is not None

    code = await pairing_manager.generate_code("jarvis-user-42")

    msg = GatewayMessage(
        sender_id="stranger",
        channel="fake",
        channel_id="c1",
        content=code,
    )
    reply = await router.handle_message(msg)
    assert reply == PAIRING_SUCCESS

    # Session should now carry the user_id
    session = await session_manager.get_or_create_session("stranger", "fake")
    assert session["user_id"] == "jarvis-user-42"


@pytest.mark.asyncio
async def test_router_unauthenticated_invalid_code_returns_error() -> None:
    """Unauthenticated sender sending an invalid 6-digit code gets the invalid msg."""
    router, _, _ = _make_router_parts()

    msg = GatewayMessage(
        sender_id="stranger", channel="fake", channel_id="c1", content="000000"
    )
    reply = await router.handle_message(msg)
    assert reply == PAIRING_INVALID


@pytest.mark.asyncio
async def test_router_unauthenticated_no_pairing_manager_returns_prompt() -> None:
    """Without a PairingManager even 6-digit messages return the pairing prompt."""
    router, _, _ = _make_router_parts(include_pairing=False)

    msg = GatewayMessage(
        sender_id="stranger", channel="fake", channel_id="c1", content="123456"
    )
    reply = await router.handle_message(msg)
    assert reply == PAIRING_PROMPT


@pytest.mark.asyncio
async def test_router_linked_user_dispatches_to_agent() -> None:
    """After pairing, subsequent messages should be routed to the agent."""
    router, _, pairing_manager = _make_router_parts()
    assert pairing_manager is not None

    # Link the user first
    code = await pairing_manager.generate_code("linked-user")
    link_msg = GatewayMessage(
        sender_id="linked-sender", channel="fake", channel_id="c1", content=code
    )
    await router.handle_message(link_msg)

    async def _fake_agent(user_id: str, message: GatewayMessage) -> str:
        return f"agent-reply-for-{user_id}"

    router._run_agent = _fake_agent  # type: ignore[method-assign]

    follow_up = GatewayMessage(
        sender_id="linked-sender",
        channel="fake",
        channel_id="c1",
        content="what time is it?",
    )
    reply = await router.handle_message(follow_up)
    assert reply == "agent-reply-for-linked-user"


@pytest.mark.asyncio
async def test_router_code_with_whitespace_is_accepted() -> None:
    """A 6-digit code surrounded by whitespace should still trigger pairing."""
    router, _, pairing_manager = _make_router_parts()
    assert pairing_manager is not None

    code = await pairing_manager.generate_code("user-whitespace")
    msg = GatewayMessage(
        sender_id="ws-sender",
        channel="fake",
        channel_id="c1",
        content=f"  {code}  ",
    )
    reply = await router.handle_message(msg)
    assert reply == PAIRING_SUCCESS
