from typing import Any

import structlog
from fastapi import APIRouter, Request, Response

from app.channels.base import BaseChannelAdapter, GatewayMessage

logger = structlog.get_logger(__name__)


class WebhookChannel(BaseChannelAdapter):
    """Generic Webhook channel adapter for third-party integrations."""

    channel_name = "webhook"

    def __init__(self) -> None:
        super().__init__()
        self.router = APIRouter()

        @self.router.post("/receive", response_model=None)
        async def handle_webhook(request: Request) -> Response | dict[str, str]:
            """Endpoint to receive messages from any external source.

            Expected JSON: {"user_id": "...", "text": "...", "reply_url": "..."}
            """
            try:
                data = await request.json()
                user_id = data.get("user_id")
                text = data.get("text")
                reply_url = data.get("reply_url")

                if not user_id or not text:
                    return Response(status_code=400, content="Missing user_id or text")

                gw_msg = GatewayMessage(
                    sender_id=user_id,
                    channel="webhook",
                    channel_id=reply_url or user_id,
                    content=text,
                )

                if self._message_handler is None:
                    return Response(content="OK", status_code=200)

                response = await self._message_handler(gw_msg)
                if response:
                    return {"reply": response}

                return Response(content="OK", status_code=200)
            except Exception:
                logger.exception("webhook_handler_error")
                return Response(status_code=500)

    async def start(self) -> None:
        logger.info("webhook_channel_ready")

    async def stop(self) -> None:
        logger.info("webhook_channel_stopped")

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """Fallback for generic webhooks."""
        logger.info(
            "webhook_outbound_triggered",
            channel_id=channel_id,
            content_len=len(content),
        )
