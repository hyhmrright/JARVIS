import asyncio
from typing import Any

import discord
import structlog

from app.gateway.models import ChannelAdapter, GatewayMessage, chunk_text

logger = structlog.get_logger(__name__)

# Discord has a 2000 character limit per message
_DISCORD_MAX_MESSAGE_LEN = 2000


class DiscordChannel(ChannelAdapter):
    """Discord bot channel adapter using discord.py."""

    channel_name = "discord"

    def __init__(self, bot_token: str) -> None:
        super().__init__()
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.bot_token = bot_token
        self._bot_task: asyncio.Task | None = None

        @self.client.event
        async def on_ready() -> None:
            logger.info("discord_channel_ready", user=str(self.client.user))

        @self.client.event
        async def on_message(message: discord.Message) -> None:
            # Ignore own messages
            if message.author == self.client.user:
                return

            # Check for DM or Mention
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = (
                self.client.user in message.mentions if self.client.user else False
            )

            if not (is_dm or is_mentioned):
                return

            # Clean content if it was a mention
            content = message.content
            if is_mentioned and self.client.user:
                content = content.replace(f"<@{self.client.user.id}>", "").strip()
                content = content.replace(f"<@!{self.client.user.id}>", "").strip()

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
                        "discord_handler_error", sender_id=gw_msg.sender_id
                    )
                    return

                if response:
                    for chunk in chunk_text(response, _DISCORD_MAX_MESSAGE_LEN):
                        await message.channel.send(chunk)

    async def start(self) -> None:
        """Start the Discord bot client in a background task."""
        if self._bot_task is not None and not self._bot_task.done():
            logger.warning("discord_channel_already_started")
            return

        self._bot_task = asyncio.create_task(self.client.start(self.bot_token))
        logger.info("discord_channel_started")

    async def stop(self) -> None:
        """Stop the Discord bot client."""
        await self.client.close()
        if self._bot_task is not None:
            self._bot_task.cancel()
            try:
                await self._bot_task
            except asyncio.CancelledError:
                pass
            self._bot_task = None
        logger.info("discord_channel_stopped")

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """Send a message to a Discord channel/DM."""
        try:
            channel = await self.client.fetch_channel(int(channel_id))
            valid_types = (
                discord.TextChannel,
                discord.DMChannel,
                discord.GroupChannel,
            )
            if isinstance(channel, valid_types):
                for chunk in chunk_text(content, _DISCORD_MAX_MESSAGE_LEN):
                    await channel.send(chunk)
        except Exception:
            logger.warning("discord_send_failed", channel_id=channel_id)
