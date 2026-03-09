"""Tests for TelegramChannel adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.telegram import _TELEGRAM_MAX_MESSAGE_LEN, TelegramChannel
from app.gateway.models import GatewayMessage

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_channel(token: str = "test:TOKEN") -> TelegramChannel:
    """Create a TelegramChannel with mocked Bot and Dispatcher internals."""
    with (
        patch("app.channels.telegram.Bot") as mock_bot_cls,
        patch("app.channels.telegram.Dispatcher") as mock_dp_cls,
    ):
        mock_bot = AsyncMock()
        mock_bot.session = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        mock_dp = MagicMock()
        mock_dp.message = MagicMock(return_value=lambda f: f)
        mock_dp.start_polling = AsyncMock(return_value=None)
        mock_dp.stop_polling = AsyncMock(return_value=None)
        mock_dp_cls.return_value = mock_dp

        return TelegramChannel(bot_token=token)


@contextmanager
def _capturing_channel() -> Iterator[tuple[TelegramChannel, list]]:
    """Yield a (channel, captured_handlers) pair.

    The channel's Dispatcher.message() decorator appends each registered
    handler to *captured_handlers*, so tests can invoke on_message directly.
    """
    captured: list = []

    def fake_decorator(f):  # noqa: ANN001
        captured.append(f)
        return f

    with (
        patch("app.channels.telegram.Bot") as mock_bot_cls,
        patch("app.channels.telegram.Dispatcher") as mock_dp_cls,
        patch("asyncio.create_task", return_value=MagicMock()),
    ):
        mock_bot = AsyncMock()
        mock_bot.session = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        mock_dp = MagicMock()
        mock_dp.message = MagicMock(return_value=fake_decorator)
        mock_dp.start_polling = AsyncMock()
        mock_dp_cls.return_value = mock_dp

        channel = TelegramChannel(bot_token="test:TOKEN")
        yield channel, captured


def _mock_tg_message(
    user_id: int = 42,
    chat_id: int = 100,
    text: str = "ping",
) -> AsyncMock:
    msg = AsyncMock()
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.chat = MagicMock()
    msg.chat.id = chat_id
    msg.text = text
    msg.reply = AsyncMock()
    return msg


# ---------------------------------------------------------------------------
# 1. Initialisation
# ---------------------------------------------------------------------------


def test_init_sets_channel_name() -> None:
    channel = _make_channel()
    assert channel.channel_name == "telegram"


def test_init_no_message_handler_by_default() -> None:
    channel = _make_channel()
    assert channel._message_handler is None


def test_init_no_polling_task_by_default() -> None:
    channel = _make_channel()
    assert channel._polling_task is None


# ---------------------------------------------------------------------------
# 2. start()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_creates_polling_task() -> None:
    channel = _make_channel()

    with (
        patch("app.channels.telegram.Bot", return_value=channel.bot),
        patch("app.channels.telegram.Dispatcher", return_value=channel.dp),
        patch("asyncio.create_task") as mock_create_task,
    ):
        channel.dp.start_polling = AsyncMock()
        channel.dp.message = MagicMock(return_value=lambda f: f)

        fake_task = MagicMock(spec=asyncio.Task)
        mock_create_task.return_value = fake_task

        await channel.start()

    assert channel._polling_task is fake_task


@pytest.mark.asyncio
async def test_start_is_idempotent() -> None:
    """Calling start() twice must not register a second handler."""
    with _capturing_channel() as (channel, captured):
        await channel.start()
        first_task = channel._polling_task

        # Second call should be a no-op
        await channel.start()

    assert channel._polling_task is first_task
    # Only one handler should have been registered
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_start_restarts_after_dead_task() -> None:
    """If the polling task has died, start() should create a new one."""
    with _capturing_channel() as (channel, _):
        dead_task = MagicMock(spec=asyncio.Task)
        dead_task.done.return_value = True
        channel._polling_task = dead_task

        await channel.start()

    assert channel._polling_task is not dead_task
    assert channel._polling_task is not None


# ---------------------------------------------------------------------------
# 3. stop()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_cancels_polling_task_and_closes_session() -> None:
    channel = _make_channel()

    # Use a real asyncio.Task that raises CancelledError when cancelled.
    async def _never_ending() -> None:
        await asyncio.sleep(3600)

    loop = asyncio.get_running_loop()
    real_task = loop.create_task(_never_ending())
    channel._polling_task = real_task

    channel.dp.stop_polling = AsyncMock()
    channel.bot.session.close = AsyncMock()

    await channel.stop()

    assert real_task.cancelled()
    channel.dp.stop_polling.assert_awaited_once()
    channel.bot.session.close.assert_awaited_once()
    assert channel._polling_task is None


# ---------------------------------------------------------------------------
# 4. send_message() — short content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_short_content_single_call() -> None:
    channel = _make_channel()
    channel.bot.send_message = AsyncMock()

    await channel.send_message(channel_id="123456", content="Hello!")

    channel.bot.send_message.assert_awaited_once_with(chat_id=123456, text="Hello!")


# ---------------------------------------------------------------------------
# 5. send_message() — long content split into chunks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_long_content_split() -> None:
    channel = _make_channel()
    channel.bot.send_message = AsyncMock()

    long_text = "x" * (_TELEGRAM_MAX_MESSAGE_LEN * 2 + 100)
    await channel.send_message(channel_id="999", content=long_text)

    # Should be called 3 times: two full chunks + one remainder
    assert channel.bot.send_message.await_count == 3
    calls = channel.bot.send_message.await_args_list
    assert calls[0].kwargs["chat_id"] == 999
    assert len(calls[0].kwargs["text"]) == _TELEGRAM_MAX_MESSAGE_LEN
    assert len(calls[1].kwargs["text"]) == _TELEGRAM_MAX_MESSAGE_LEN
    assert len(calls[2].kwargs["text"]) == 100


@pytest.mark.asyncio
async def test_send_message_invalid_channel_id_logs_and_returns() -> None:
    """A non-numeric channel_id must log an error and not raise."""
    channel = _make_channel()
    channel.bot.send_message = AsyncMock()

    await channel.send_message(channel_id="not-a-number", content="hi")

    channel.bot.send_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# 6. on_message handler wired in start()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_message_calls_handler_and_replies() -> None:
    """When a message arrives, the registered handler should be called and the
    reply sent back via message.reply()."""
    with _capturing_channel() as (channel, captured):
        await channel.start()

    assert captured, "on_message decorator was not called"
    on_message = captured[0]

    mock_msg = _mock_tg_message()

    async def my_handler(msg: GatewayMessage) -> str:
        return "pong"

    channel.set_message_handler(my_handler)
    await on_message(mock_msg)

    mock_msg.reply.assert_awaited_once_with("pong")


# ---------------------------------------------------------------------------
# 7. on_message ignores messages with no text or no user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_message_ignores_no_text() -> None:
    with _capturing_channel() as (channel, captured):
        await channel.start()

    on_message = captured[0]

    handler_called = False

    async def my_handler(msg: GatewayMessage) -> str:
        nonlocal handler_called
        handler_called = True
        return "reply"

    channel.set_message_handler(my_handler)

    # No text
    mock_no_text = AsyncMock()
    mock_no_text.from_user = MagicMock()
    mock_no_text.text = None
    await on_message(mock_no_text)

    # No user
    mock_no_user = AsyncMock()
    mock_no_user.from_user = None
    mock_no_user.text = "hi"
    await on_message(mock_no_user)

    assert not handler_called, "Handler must not be called for invalid messages"


# ---------------------------------------------------------------------------
# 8. on_message handler exception is caught, not propagated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_message_handler_exception_does_not_propagate() -> None:
    """If the message handler raises, on_message should catch it and return."""
    with _capturing_channel() as (channel, captured):
        await channel.start()

    on_message = captured[0]
    mock_msg = _mock_tg_message()

    async def crashing_handler(msg: GatewayMessage) -> str:
        raise RuntimeError("boom")

    channel.set_message_handler(crashing_handler)

    # Must not raise
    await on_message(mock_msg)

    # No reply should have been sent
    mock_msg.reply.assert_not_awaited()


# ---------------------------------------------------------------------------
# 9. set_message_handler (inherited from ChannelAdapter)
# ---------------------------------------------------------------------------


def test_set_message_handler_stores_handler() -> None:
    channel = _make_channel()

    async def my_handler(msg: GatewayMessage) -> str:
        return "ok"

    channel.set_message_handler(my_handler)
    assert channel._message_handler is my_handler


# ---------------------------------------------------------------------------
# 10. Webhook Support
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telegram_webhook_handling():
    """验证 Telegram Webhook 路由是否能正确处理更新。"""
    with (
        patch("app.channels.telegram.Bot"),
        patch("app.channels.telegram.Dispatcher") as mock_dp_class,
    ):
        mock_dp = mock_dp_class.return_value
        mock_dp.feed_update = AsyncMock()

        adapter = TelegramChannel("token", webhook_url="http://example.com")

        # Simulate request
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(
            return_value={
                "update_id": 123,
                "message": {
                    "message_id": 456,
                    "date": 123456789,
                    "chat": {"id": 100, "type": "private"},
                    "text": "hi",
                },
            }
        )

        # Call handle_update directly (it's inside _setup_router)
        # We need to find the route in adapter.router
        handle_update = adapter.router.routes[0].endpoint
        response = await handle_update(mock_request)

        assert response.status_code == 200
        mock_dp.feed_update.assert_called_once()


@pytest.mark.asyncio
async def test_telegram_start_sets_webhook():
    """验证 start() 在有 webhook_url 时设置 webhook。"""
    with (
        patch("app.channels.telegram.Bot") as mock_bot_class,
        patch("app.channels.telegram.Dispatcher"),
    ):
        mock_bot = mock_bot_class.return_value
        mock_bot.set_webhook = AsyncMock()

        adapter = TelegramChannel("token", webhook_url="http://example.com")
        await adapter.start()

        mock_bot.set_webhook.assert_called_once_with(
            url="http://example.com/api/channels/telegram/webhook"
        )
