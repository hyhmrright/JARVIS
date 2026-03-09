from typing import Any

import structlog
from fastapi import APIRouter, Request, Response
from twilio.rest import Client

from app.channels.base import BaseChannelAdapter, GatewayMessage, chunk_text

logger = structlog.get_logger(__name__)

# WhatsApp has a 1600 character limit per message for Twilio
_WHATSAPP_MAX_MESSAGE_LEN = 1600


class WhatsAppChannel(BaseChannelAdapter):
    """WhatsApp bot channel adapter using Twilio Webhooks."""

    channel_name = "whatsapp"

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
                channel_id=sender_id,  # WhatsApp uses phone number as channel ID
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

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """Send a message to a WhatsApp user via Twilio."""
        try:
            for chunk in chunk_text(content, _WHATSAPP_MAX_MESSAGE_LEN):
                self.client.messages.create(
                    body=chunk, from_=self.from_number, to=channel_id
                )
        except Exception:
            logger.warning("whatsapp_send_failed", channel_id=channel_id)
