import asyncio
import re
from typing import Any

import structlog
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.app.async_app import AsyncApp

from app.gateway.models import ChannelAdapter, GatewayMessage, chunk_text

logger = structlog.get_logger(__name__)

_SLACK_MAX_MESSAGE_LEN = 4000


class SlackChannel(ChannelAdapter):
    """Slack bot channel adapter using Socket Mode (AsyncBolt)."""

    channel_name = "slack"

    def __init__(self, bot_token: str, app_token: str) -> None:
        super().__init__()
        self.app = AsyncApp(token=bot_token)
        self.app_token = app_token
        self._handler: AsyncSocketModeHandler | None = None
        self._polling_task: asyncio.Task | None = None

        @self.app.event("app_mention")
        async def handle_mention(event: dict[str, Any], say: Any) -> None:
            await self._on_slack_message(event, say)

        @self.app.message(re.compile(".*"))
        async def handle_message(event: dict[str, Any], say: Any) -> None:
            # Only respond to direct messages (DMs) to avoid noise in channels
            if event.get("channel_type") == "im":
                await self._on_slack_message(event, say)

    async def _on_slack_message(self, event: dict[str, Any], say: Any) -> None:
        user_id = event.get("user")
        text = event.get("text")
        channel_id = event.get("channel")
        if not user_id or not text or not channel_id:
            return

        # Clean up mention from text if present
        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        if not text:
            return

        gw_msg = GatewayMessage(
            sender_id=user_id,
            channel="slack",
            channel_id=channel_id,
            content=text,
        )

        if self._message_handler is not None:
            try:
                response = await self._message_handler(gw_msg)
            except Exception:
                logger.exception("slack_handler_error", sender_id=user_id)
                return

            if response:
                for chunk in chunk_text(response, _SLACK_MAX_MESSAGE_LEN):
                    await say(text=chunk)

    async def start(self) -> None:
        """Start the Slack Socket Mode handler in a background task."""
        if self._polling_task is not None and not self._polling_task.done():
            logger.warning("slack_channel_already_started")
            return

        self._handler = AsyncSocketModeHandler(self.app, self.app_token)
        self._polling_task = asyncio.create_task(self._handler.start_async())
        logger.info("slack_channel_started")

    async def stop(self) -> None:
        """Stop the Socket Mode handler."""
        if self._handler is not None:
            await self._handler.close_async()
            self._handler = None
        if self._polling_task is not None:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None
        logger.info("slack_channel_stopped")

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """Send a message to a Slack channel/DM."""
        try:
            for chunk in chunk_text(content, _SLACK_MAX_MESSAGE_LEN):
                await self.app.client.chat_postMessage(channel=channel_id, text=chunk)
        except Exception:
            logger.warning("slack_send_failed", channel_id=channel_id)
