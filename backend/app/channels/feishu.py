import asyncio
from typing import Any

import structlog

from fastapi import APIRouter, Request, Response

from app.channels.base import BaseChannelAdapter, GatewayMessage, chunk_text

logger = structlog.get_logger(__name__)

_FEISHU_MAX_MESSAGE_LEN = 20000  # Feishu/Lark limits


class FeishuChannel(BaseChannelAdapter):
    """Feishu (Lark) bot channel adapter.

    Inspired by OpenClaw's Feishu extension.
    """

    channel_name = "feishu"

    def __init__(
        self, app_id: str, app_secret: str, verification_token: str | None = None
    ) -> None:
        super().__init__()
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token
        self.router = APIRouter()
        self._webhook_task: asyncio.Task | None = None
        self._handler_registered = False
        self._setup_router()

    def _setup_router(self) -> None:
        @self.router.post("/webhook")
        async def handle_webhook(request: Request) -> Response | dict[str, Any]:
            # Basic Feishu verification and event handling stub
            try:
                data = await request.json()
                # URL verification
                if data.get("type") == "url_verification":
                    return {"challenge": data.get("challenge")}
                
                # Event handling logic would go here
                logger.info("feishu_webhook_received", event_type=data.get("header", {}).get("event_type"))
                return {"status": "ok"}
            except Exception:
                logger.exception("feishu_webhook_error")
                return Response(status_code=500)

    async def start(self) -> None:
        """Start the Feishu event listener."""
        if self._webhook_task is not None and not self._webhook_task.done():
            logger.warning("feishu_channel_already_started")
            return

        if not self._handler_registered:
            self._handler_registered = True
            logger.info("feishu_handler_registered", app_id=self.app_id)
            # Webhook routing would typically be handled by the FastAPI app directly
            # This is a stub for the event loop task

        # Mocking the background task for webhook event polling/queue processing
        async def _mock_event_loop() -> None:
            while True:
                await asyncio.sleep(3600)

        self._webhook_task = asyncio.create_task(_mock_event_loop())
        logger.info("feishu_channel_started")

    async def stop(self) -> None:
        """Stop the Feishu channel."""
        if self._webhook_task is not None:
            self._webhook_task.cancel()
            try:
                await self._webhook_task
            except asyncio.CancelledError:
                pass
            self._webhook_task = None
        logger.info("feishu_channel_stopped")

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """Send a message to a Feishu chat."""
        try:
            for chunk in chunk_text(content, _FEISHU_MAX_MESSAGE_LEN):
                # Stub: send via Feishu OpenAPI
                # request = lark.im.v1.CreateMessageRequest.builder() \\
                #     .receive_id_type("chat_id").request_body(...)
                # await self.client.im.v1.message.acreate(request)
                logger.debug(
                    "feishu_send_stub",
                    chat_id=channel_id,
                    chunk_length=len(chunk),
                )
        except Exception:
            logger.exception("feishu_send_failed", channel_id=channel_id)
