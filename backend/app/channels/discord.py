import asyncio
from typing import Any

import discord
import structlog

from app.channels.base import BaseChannelAdapter, GatewayMessage

logger = structlog.get_logger(__name__)


class DiscordChannel(BaseChannelAdapter):
    """使用 discord.py 的 Discord 机器人渠道适配器。"""

    channel_name = "discord"
    # Discord 每条消息有 2000 字符的限制
    max_message_length = 2000

    def __init__(self, bot_token: str) -> None:
        super().__init__()
        self._bot_token = bot_token
        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)
        self._task: asyncio.Task | None = None
        self._setup_events()

    def _setup_events(self) -> None:
        self._client.event(self._on_ready)
        self._client.event(self._on_message)

    async def _on_ready(self) -> None:
        logger.info("discord_channel_ready", user=str(self._client.user))

    async def _on_message(self, message: discord.Message) -> None:
        # 忽略机器人自身的消息
        if message.author == self._client.user:
            return
        if not message.content:
            return

        # 检查是否为私聊或被提及
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = (
            self._client.user in message.mentions if self._client.user else False
        )

        # 仅在私聊或机器人被提及的情况下进行处理
        if not (is_dm or is_mentioned):
            return

        # 如果是被提及，则清理内容中的提及信息
        content = message.content
        if is_mentioned and self._client.user:
            content = content.replace(f"<@{self._client.user.id}>", "").strip()
            content = content.replace(f"<@!{self._client.user.id}>", "").strip()

        gw_msg = GatewayMessage(
            sender_id=str(message.author.id),
            channel="discord",
            channel_id=str(message.channel.id),
            content=content,
        )

        if self._message_handler is not None:
            try:
                response = await self._message_handler(gw_msg)
            except Exception:
                logger.exception(
                    "discord_handler_error",
                    sender_id=gw_msg.sender_id,
                )
                return
            if response:
                await self.send_message(str(message.channel.id), response)

    async def start(self) -> None:
        """在后台启动 Discord 客户端。

        幂等性：如果客户端已经在运行，则后续调用不执行任何操作。
        """
        if self._task is not None and not self._task.done():
            logger.warning("discord_channel_already_started")
            return
        if self._task is not None:
            logger.warning("discord_task_died_restarting")
            self._task = None

        self._task = asyncio.create_task(self._client.start(self._bot_token))
        logger.info("discord_channel_started")

    async def stop(self) -> None:
        """关闭 Discord 客户端并取消后台任务。"""
        await self._client.close()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("discord_channel_stopped")

    async def _send_raw_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """发送原始消息块到 Discord 频道。"""
        try:
            cid = int(channel_id)
            channel = self._client.get_channel(cid)
            if channel is None:
                channel = await self._client.fetch_channel(cid)

            if isinstance(channel, discord.abc.Messageable):
                await channel.send(content)
            else:
                logger.warning("discord_channel_not_messageable", channel_id=channel_id)
        except (ValueError, Exception):
            # 向上抛出异常，由基类记录
            raise
