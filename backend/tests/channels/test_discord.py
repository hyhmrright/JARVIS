"""Tests for DiscordChannel adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from app.channels.base import GatewayMessage
from app.channels.discord import DiscordChannel

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_channel(token: str = "test_token") -> DiscordChannel:
    """Create a DiscordChannel with mocked discord.Client internals."""
    with (
        patch("app.channels.discord.discord.Client") as mock_client_cls,
        patch("app.channels.discord.discord.Intents") as mock_intents_cls,
    ):
        mock_intents = MagicMock()
        mock_intents_cls.default.return_value = mock_intents

        mock_client = MagicMock()
        mock_client.user = MagicMock()
        mock_client.event = lambda f: f
        mock_client.start = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_channel = MagicMock(return_value=None)
        mock_client.fetch_channel = AsyncMock()
        mock_client_cls.return_value = mock_client

        return DiscordChannel(bot_token=token)


@contextmanager
def _capturing_channel() -> Iterator[tuple[DiscordChannel, dict]]:
    """Yield a (channel, handlers) pair.

    The handlers dict contains 'on_message' and 'on_ready' callables registered
    via the client.event(func) call.
    """
    captured: dict = {}

    def fake_event(f):  # noqa: ANN001
        captured[f.__name__] = f
        return f

    with (
        patch("app.channels.discord.discord.Client") as mock_client_cls,
        patch("app.channels.discord.discord.Intents") as mock_intents_cls,
        patch("asyncio.create_task", return_value=MagicMock()),
    ):
        mock_intents = MagicMock()
        mock_intents_cls.default.return_value = mock_intents

        mock_client = MagicMock()
        mock_client.user = MagicMock()
        mock_client.event = fake_event
        mock_client.start = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client_cls.return_value = mock_client

        channel = DiscordChannel(bot_token="test_token")
        yield channel, captured


def _mock_discord_message(
    author_id: int = 42,
    channel_id: int = 100,
    content: str = "ping",
    is_self: bool = False,
) -> MagicMock:
    msg = MagicMock()
    msg.author = MagicMock()
    msg.author.id = author_id
    msg.channel = MagicMock()
    msg.channel.id = channel_id
    msg.channel.send = AsyncMock()
    msg.content = content
    # is_self is determined by comparing message.author == client.user;
    # the test sets this up externally.
    return msg


# ---------------------------------------------------------------------------
# 1. Initialisation
# ---------------------------------------------------------------------------


def test_init_sets_channel_name() -> None:
    channel = _make_channel()
    assert channel.channel_name == "discord"


def test_init_no_message_handler_by_default() -> None:
    channel = _make_channel()
    assert channel._message_handler is None


def test_init_no_task_by_default() -> None:
    channel = _make_channel()
    assert channel._task is None


# ---------------------------------------------------------------------------
# 2. start()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_creates_background_task() -> None:
    channel = _make_channel()

    with patch("asyncio.create_task") as mock_create_task:
        fake_task = MagicMock(spec=asyncio.Task)
        mock_create_task.return_value = fake_task
        channel._client.start = AsyncMock()

        await channel.start()

    assert channel._task is fake_task


@pytest.mark.asyncio
async def test_start_is_idempotent() -> None:
    """Calling start() twice must not create a second background task."""
    with _capturing_channel() as (channel, _):
        await channel.start()
        first_task = channel._task

        # Second call should be a no-op
        await channel.start()

    assert channel._task is first_task


@pytest.mark.asyncio
async def test_start_restarts_after_dead_task() -> None:
    """If the background task has died, start() should create a new one."""
    channel = _make_channel()

    dead_task = MagicMock(spec=asyncio.Task)
    dead_task.done.return_value = True
    channel._task = dead_task

    with patch("asyncio.create_task") as mock_create_task:
        new_task = MagicMock(spec=asyncio.Task)
        mock_create_task.return_value = new_task
        channel._client.start = AsyncMock()

        await channel.start()

    assert channel._task is new_task
    mock_create_task.assert_called_once()


# ---------------------------------------------------------------------------
# 3. stop()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_closes_client_and_cancels_task() -> None:
    channel = _make_channel()

    async def _never_ending() -> None:
        await asyncio.sleep(3600)

    loop = asyncio.get_running_loop()
    real_task = loop.create_task(_never_ending())
    channel._task = real_task

    await channel.stop()

    assert real_task.cancelled()
    channel._client.close.assert_awaited_once()
    assert channel._task is None


# ---------------------------------------------------------------------------
# 4. send_message() — short content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_short_content_single_call() -> None:
    channel = _make_channel()

    mock_text_channel = AsyncMock(spec=discord.TextChannel)
    mock_text_channel.send = AsyncMock()
    channel._client.get_channel = MagicMock(return_value=mock_text_channel)

    await channel.send_message(channel_id="123456", content="Hello!")

    mock_text_channel.send.assert_awaited_once_with("Hello!")


# ---------------------------------------------------------------------------
# 5. send_message() — long content split into chunks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_long_content_split() -> None:
    channel = _make_channel()

    mock_text_channel = AsyncMock(spec=discord.TextChannel)
    mock_text_channel.send = AsyncMock()
    channel._client.get_channel = MagicMock(return_value=mock_text_channel)

    long_text = "x" * (DiscordChannel.max_message_length * 2 + 100)
    await channel.send_message(channel_id="999", content=long_text)

    # Should be called 3 times: two full chunks + one remainder
    assert mock_text_channel.send.await_count == 3
    calls = mock_text_channel.send.await_args_list
    assert len(calls[0].args[0]) == DiscordChannel.max_message_length
    assert len(calls[1].args[0]) == DiscordChannel.max_message_length
    assert len(calls[2].args[0]) == 100


# ---------------------------------------------------------------------------
# 6. send_message() — invalid channel_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_invalid_channel_id_logs_and_returns() -> None:
    """A non-numeric channel_id must log a warning and not raise."""
    channel = _make_channel()
    channel._client.get_channel = MagicMock()

    await channel.send_message(channel_id="not-a-number", content="hi")

    channel._client.get_channel.assert_not_called()


# ---------------------------------------------------------------------------
# 7. on_message handler wired via _setup_events()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_message_calls_handler_and_sends_reply() -> None:
    """When a message arrives, the handler is called and the reply is sent."""
    with _capturing_channel() as (channel, captured):
        pass  # _setup_events() already ran during __init__

    assert "_on_message" in captured, "_on_message was not registered"
    on_message = captured["_on_message"]

    mock_msg = _mock_discord_message()
    # author != client.user so it's not ignored
    mock_msg.author = MagicMock()
    channel._client.user = MagicMock()

    # Mock mention
    mock_msg.mentions = [channel._client.user]
    mock_msg.channel = MagicMock(spec=discord.TextChannel)

    async def my_handler(msg: GatewayMessage) -> str:
        return "pong"

    channel.set_message_handler(my_handler)
    channel.send_message = AsyncMock()
    await on_message(mock_msg)

    channel.send_message.assert_awaited_once_with(str(mock_msg.channel.id), "pong")


# ---------------------------------------------------------------------------
# 8. on_message ignores own messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_message_ignores_self_messages() -> None:
    with _capturing_channel() as (channel, captured):
        pass

    on_message = captured["_on_message"]

    handler_called = False

    async def my_handler(msg: GatewayMessage) -> str:
        nonlocal handler_called
        handler_called = True
        return "reply"

    channel.set_message_handler(my_handler)

    # Simulate a message from the bot itself
    mock_msg = _mock_discord_message()
    mock_msg.author = channel._client.user  # same object → equality check passes

    await on_message(mock_msg)

    assert not handler_called, "Handler must not be called for the bot's own messages"


# ---------------------------------------------------------------------------
# 9. on_message ignores empty content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_message_ignores_empty_content() -> None:
    with _capturing_channel() as (channel, captured):
        pass

    on_message = captured["_on_message"]

    handler_called = False

    async def my_handler(msg: GatewayMessage) -> str:
        nonlocal handler_called
        handler_called = True
        return "reply"

    channel.set_message_handler(my_handler)

    mock_msg = _mock_discord_message(content="")
    mock_msg.author = MagicMock()  # not self
    channel._client.user = MagicMock()

    await on_message(mock_msg)

    assert not handler_called, "Handler must not be called for empty content"


# ---------------------------------------------------------------------------
# 10. on_message handler exception is caught, not propagated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_message_handler_exception_does_not_propagate() -> None:
    """If the message handler raises, on_message should catch it and return."""
    with _capturing_channel() as (channel, captured):
        pass

    on_message = captured["_on_message"]
    mock_msg = _mock_discord_message()
    mock_msg.author = MagicMock()
    channel._client.user = MagicMock()

    # Mock mention
    mock_msg.mentions = [channel._client.user]
    mock_msg.channel = MagicMock(spec=discord.TextChannel)

    async def crashing_handler(msg: GatewayMessage) -> str:
        raise RuntimeError("boom")

    channel.set_message_handler(crashing_handler)

    # Must not raise
    await on_message(mock_msg)

    # No reply should have been sent
    mock_msg.channel.send.assert_not_awaited()


# ---------------------------------------------------------------------------
# 11. set_message_handler (inherited from BaseChannelAdapter)
# ---------------------------------------------------------------------------


def test_set_message_handler_stores_handler() -> None:
    channel = _make_channel()

    async def my_handler(msg: GatewayMessage) -> str:
        return "ok"

    channel.set_message_handler(my_handler)
    assert channel._message_handler is my_handler
