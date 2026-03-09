import asyncio
from typing import Any

import discord
import structlog

from app.channels.base import BaseChannelAdapter, GatewayMessage, chunk_text

logger = structlog.get_logger(__name__)

# Discord has a 2000 character limit per message
_DISCORD_MAX_MESSAGE_LEN = 2000


class DiscordChannel(BaseChannelAdapter):
    """Discord bot channel adapter using discord.py."""

    channel_name = "discord"

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
        # Ignore own messages
        if message.author == self._client.user:
            return
        if not message.content:
            return

        # Check for DM or Mention
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = (
            self._client.user in message.mentions if self._client.user else False
        )

        # Process only if it's a DM or the bot is mentioned
        if not (is_dm or is_mentioned):
            return

        # Clean content if it was a mention
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
                for chunk in chunk_text(response, _DISCORD_MAX_MESSAGE_LEN):
                    await message.channel.send(chunk)

    async def start(self) -> None:
        """Start the Discord client in the background.

        Idempotent: subsequent calls are no-ops if the client is already running.
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
        """Close the Discord client and cancel the background task."""
        await self._client.close()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("discord_channel_stopped")

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """Send a message to a Discord channel, splitting if over 2000 chars."""
        try:
            cid = int(channel_id)
        except ValueError:
            logger.warning("discord_invalid_channel_id", channel_id=channel_id)
            return
        
        try:
            channel = self._client.get_channel(cid)
            if channel is None:
                channel = await self._client.fetch_channel(cid)
        except Exception:
            logger.warning("discord_channel_fetch_failed", channel_id=channel_id)
            return
            
        if not isinstance(channel, discord.abc.Messageable):
            logger.warning("discord_channel_not_messageable", channel_id=channel_id)
            return
            
        try:
            for chunk in chunk_text(content, _DISCORD_MAX_MESSAGE_LEN):
                await channel.send(chunk)
        except Exception:
            logger.warning("discord_send_failed", channel_id=channel_id)
