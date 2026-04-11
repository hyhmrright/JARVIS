from typing import Any

import structlog
from fastapi import APIRouter, Request, Response
from twilio.rest import Client

from app.channels.base import BaseChannelAdapter, GatewayMessage

logger = structlog.get_logger(__name__)


class WhatsAppChannel(BaseChannelAdapter):
    """使用 Twilio Webhooks 的 WhatsApp 机器人渠道适配器。"""

    channel_name = "whatsapp"
    # WhatsApp (Twilio) 的消息长度限制为 1600 字符
    max_message_length = 1600

    def __init__(self, account_sid: str, auth_token: str, from_number: str) -> None:
        super().__init__()
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number
        self.router = APIRouter()

        @self.router.post("/webhook")
        async def handle_webhook(request: Request) -> Response:
            form_data = await request.form()
            sender_id = str(form_data.get("From", ""))
            content = str(form_data.get("Body", ""))

            if not sender_id or not content:
                return Response(status_code=400)

            gw_msg = GatewayMessage(
                sender_id=sender_id,
                channel="whatsapp",
                channel_id=sender_id,  # WhatsApp 使用电话号码作为渠道 ID
                content=content,
            )

            if self._message_handler is not None:
                try:
                    response = await self._message_handler(gw_msg)
                except Exception:
                    logger.exception("whatsapp_handler_error", sender_id=sender_id)
                    return Response(status_code=500)

                if response:
                    await self.send_message(sender_id, response)

            return Response(content="OK", status_code=200)

    async def start(self) -> None:
        logger.info("whatsapp_channel_ready_via_webhook")

    async def stop(self) -> None:
        logger.info("whatsapp_channel_stopped")

    async def _send_raw_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """通过 Twilio 发送消息给 WhatsApp 用户。"""
        self.client.messages.create(body=content, from_=self.from_number, to=channel_id)
