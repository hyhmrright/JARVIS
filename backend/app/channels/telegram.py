import asyncio
from typing import Any

import structlog
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.gateway.models import ChannelAdapter, GatewayMessage, chunk_text

logger = structlog.get_logger(__name__)

_TELEGRAM_MAX_MESSAGE_LEN = 4096


class TelegramChannel(ChannelAdapter):
    """Telegram bot channel adapter using aiogram long-polling."""

    channel_name = "telegram"

    def __init__(self, bot_token: str) -> None:
        super().__init__()
        self.bot = Bot(
            token=bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher()
        self._polling_task: asyncio.Task | None = None
        self._handler_registered = False

    async def start(self) -> None:
        """Register the message handler and start long-polling in the background.

        Idempotent: subsequent calls are no-ops if polling is already running.
        """
        if self._polling_task is not None and not self._polling_task.done():
            logger.warning("telegram_channel_already_started")
            return
        if self._polling_task is not None:
            logger.warning("telegram_task_died_restarting")
            self._polling_task = None

        if not self._handler_registered:
            self._handler_registered = True

            @self.dp.message()
            async def on_message(message: types.Message) -> None:
                if not message.from_user or not message.text:
                    return
                gw_msg = GatewayMessage(
                    sender_id=str(message.from_user.id),
                    channel="telegram",
                    channel_id=str(message.chat.id),
                    content=message.text,
                )
                if self._message_handler is not None:
                    try:
                        response = await self._message_handler(gw_msg)
                    except Exception:
                        logger.exception(
                            "telegram_handler_error",
                            sender_id=gw_msg.sender_id,
                        )
                        return
                    if response:
                        for chunk in chunk_text(response, _TELEGRAM_MAX_MESSAGE_LEN):
                            await message.reply(chunk)

        self._polling_task = asyncio.create_task(self.dp.start_polling(self.bot))
        logger.info("telegram_channel_started")

    async def stop(self) -> None:
        """Stop long-polling and release the bot session."""
        await self.dp.stop_polling()
        if self._polling_task is not None:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None
        await self.bot.session.close()
        logger.info("telegram_channel_stopped")

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """Send a message to a Telegram chat, splitting if over 4096 chars."""
        try:
            chat_id = int(channel_id)
        except ValueError:
            logger.warning("telegram_invalid_channel_id", channel_id=channel_id)
            return
        try:
            for chunk in chunk_text(content, _TELEGRAM_MAX_MESSAGE_LEN):
                await self.bot.send_message(chat_id=chat_id, text=chunk)
        except Exception:
            logger.warning("telegram_send_failed", channel_id=channel_id)
