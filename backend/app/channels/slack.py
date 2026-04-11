import asyncio
import re
from typing import Any

import structlog
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.app.async_app import AsyncApp

from app.channels.base import BaseChannelAdapter, GatewayMessage

logger = structlog.get_logger(__name__)


class SlackChannel(BaseChannelAdapter):
    """使用 Socket Mode (AsyncBolt) 的 Slack 机器人渠道适配器。"""

    channel_name = "slack"
    max_message_length = 4000

    def __init__(self, bot_token: str, app_token: str) -> None:
        super().__init__()
        self.app = AsyncApp(token=bot_token)
        self.app_token = app_token
        self._handler: AsyncSocketModeHandler | None = None
        self._polling_task: asyncio.Task | None = None

        @self.app.event("app_mention")
        async def handle_mention(event: dict[str, Any], say: Any) -> None:
            await self._on_slack_message(event)

        @self.app.message(re.compile(".*"))
        async def handle_message(event: dict[str, Any], say: Any) -> None:
            # 仅响应直接消息 (DM)，以避免频道中的噪音
            if event.get("channel_type") == "im":
                await self._on_slack_message(event)

    async def _on_slack_message(self, event: dict[str, Any]) -> None:
        user_id = event.get("user")
        text = event.get("text")
        channel_id = event.get("channel")
        if not user_id or not text or not channel_id:
            return

        # 如果存在提及，则从文本中清除提及
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
                await self.send_message(channel_id, response)

    async def start(self) -> None:
        """在后台任务中启动 Slack Socket Mode 处理程序。"""
        if self._polling_task is not None and not self._polling_task.done():
            logger.warning("slack_channel_already_started")
            return

        self._handler = AsyncSocketModeHandler(self.app, self.app_token)
        self._polling_task = asyncio.create_task(self._handler.start_async())
        logger.info("slack_channel_started")

    async def stop(self) -> None:
        """停止 Socket Mode 处理程序。"""
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

    async def _send_raw_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """发送消息到 Slack 频道或直接消息。"""
        try:
            await self.app.client.chat_postMessage(channel=channel_id, text=content)
        except Exception:
            logger.warning("slack_send_failed", channel_id=channel_id)
