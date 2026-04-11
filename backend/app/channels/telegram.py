import asyncio
from typing import Any

import structlog
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import APIRouter, Request, Response

from app.channels.base import BaseChannelAdapter, GatewayMessage

logger = structlog.get_logger(__name__)


class TelegramChannel(BaseChannelAdapter):
    """使用 aiogram 的 Telegram 机器人渠道适配器。

    支持长轮询和 Webhook 两种模式。
    """

    channel_name = "telegram"
    max_message_length = 4096

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
                    if response:
                        # 使用基类方法发送，自动处理分块
                        await self.send_message(str(message.chat.id), response)
                except Exception:
                    logger.exception(
                        "telegram_handler_error",
                        sender_id=gw_msg.sender_id,
                    )

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
        """启动适配器。"""
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
        """停止适配器并释放资源。"""
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

    async def _send_raw_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """调用 Telegram API 发送原始消息块。"""
        try:
            chat_id = int(channel_id)
            await self.bot.send_message(chat_id=chat_id, text=content)
        except ValueError:
            logger.warning("telegram_invalid_chat_id", channel_id=channel_id)
        except Exception:
            # 基类会捕获并记录完整异常，此处仅需向上抛出
            raise
