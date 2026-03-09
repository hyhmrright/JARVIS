import asyncio
from typing import Any

import structlog
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import APIRouter, Request, Response

from app.channels.base import BaseChannelAdapter, GatewayMessage, chunk_text

logger = structlog.get_logger(__name__)

_TELEGRAM_MAX_MESSAGE_LEN = 4096


class TelegramChannel(BaseChannelAdapter):
    """Telegram bot channel adapter using aiogram.

    Supports both long-polling and Webhooks.
    """

    channel_name = "telegram"

    def __init__(self, bot_token: str, webhook_url: str | None = None) -> None:
        super().__init__()
        self.bot = Bot(
            token=bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher()
        self.webhook_url = webhook_url
        self.router = APIRouter()
        self._polling_task: asyncio.Task | None = None
        self._handler_registered = False
        self._setup_handlers()
        self._setup_router()

    def _setup_handlers(self) -> None:
        if self._handler_registered:
            return
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

    def _setup_router(self) -> None:
        @self.router.post("/webhook")
        async def handle_update(request: Request) -> Response:
            if not self.webhook_url:
                return Response(status_code=404)

            try:
                update_data = await request.json()
                update = types.Update(**update_data)
                await self.dp.feed_update(self.bot, update)
                return Response(content="OK", status_code=200)
            except Exception:
                logger.exception("telegram_webhook_error")
                return Response(status_code=500)

    async def start(self) -> None:
        """Start the channel adapter.

        If webhook_url is provided, it sets the webhook.
        Otherwise, it starts long-polling in the background.
        """
        if self.webhook_url:
            webhook_path = (
                f"{self.webhook_url.rstrip('/')}/api/channels/telegram/webhook"
            )
            await self.bot.set_webhook(url=webhook_path)
            logger.info("telegram_webhook_set", url=webhook_path)
        else:
            if self._polling_task is not None and not self._polling_task.done():
                logger.warning("telegram_channel_already_started")
                return
            self._polling_task = asyncio.create_task(self.dp.start_polling(self.bot))
            logger.info("telegram_polling_started")

    async def stop(self) -> None:
        """Stop long-polling or delete webhook, and release the bot session."""
        if self.webhook_url:
            await self.bot.delete_webhook()
            logger.info("telegram_webhook_deleted")
        else:
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
        """Send a message back to the channel."""
        try:
            chat_id = int(channel_id)
        except ValueError:
            logger.warning("telegram_invalid_chat_id", channel_id=channel_id)
            return

        try:
            for chunk in chunk_text(content, _TELEGRAM_MAX_MESSAGE_LEN):
                await self.bot.send_message(chat_id=chat_id, text=chunk)
        except Exception:
            logger.warning("telegram_send_failed", channel_id=channel_id)
