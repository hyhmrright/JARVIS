import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.channels.slack import SlackChannel
from app.channels.base import GatewayMessage


@pytest.mark.asyncio
async def test_slack_init():
    with patch("app.channels.slack.AsyncApp"):
        channel = SlackChannel("bot-token", "app-token")
        assert channel.channel_name == "slack"
        assert channel.app_token == "app-token"


@pytest.mark.asyncio
async def test_slack_on_message_flow():
    with patch("app.channels.slack.AsyncApp"):
        channel = SlackChannel("bot-token", "app-token")

        # Mock message handler
        async def my_handler(msg: GatewayMessage) -> str:
            assert msg.content == "hello"
            return "pong"

        channel.set_message_handler(my_handler)

        # Simulate event and say
        event = {
            "user": "U123",
            "text": "hello",
            "channel": "C123",
            "channel_type": "im",
        }
        mock_say = AsyncMock()

        await channel._on_slack_message(event, mock_say)

        mock_say.assert_awaited_once_with(text="pong")


@pytest.mark.asyncio
async def test_slack_start_stop():
    with patch("app.channels.slack.AsyncApp"), patch(
        "app.channels.slack.AsyncSocketModeHandler"
    ) as mock_handler_cls:
        mock_handler = mock_handler_cls.return_value

        # start_async must return a coroutine
        async def _fake_start():
            await asyncio.sleep(3600)

        mock_handler.start_async = MagicMock(return_value=_fake_start())
        mock_handler.close_async = AsyncMock()

        channel = SlackChannel("bot-token", "app-token")

        await channel.start()
        assert channel._handler is not None
        assert channel._polling_task is not None

        await channel.stop()
        mock_handler.close_async.assert_awaited_once()
        assert channel._handler is None
        assert channel._polling_task is None
