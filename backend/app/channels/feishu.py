import asyncio
import json
from typing import Any

import structlog
import httpx
from fastapi import APIRouter, Request, Response

from app.channels.base import BaseChannelAdapter, GatewayMessage, chunk_text

logger = structlog.get_logger(__name__)

_FEISHU_MAX_MESSAGE_LEN = 20000  # Feishu/Lark limits


class FeishuChannel(BaseChannelAdapter):
    """Feishu (Lark) bot channel adapter with Webhook and API support."""

    channel_name = "feishu"

    def __init__(
        self, app_id: str, app_secret: str, verification_token: str | None = None
    ) -> None:
        super().__init__()
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token
        self.router = APIRouter()
        self._tenant_token: str | None = None
        self._token_expiry: float = 0
        self._setup_router()

    async def _get_tenant_token(self) -> str:
        """Get or refresh the tenant access token."""
        import time
        if self._tenant_token and time.time() < self._token_expiry:
            return self._tenant_token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={
                "app_id": self.app_id,
                "app_secret": self.app_secret
            })
            resp.raise_for_status()
            data = resp.json()
            self._tenant_token = data["tenant_access_token"]
            self._token_expiry = time.time() + data["expire"] - 60
            return self._tenant_token

    def _setup_router(self) -> None:
        @self.router.post("/webhook")
        async def handle_webhook(request: Request) -> Any:
            try:
                data = await request.json()
                
                # 1. URL Verification
                if data.get("type") == "url_verification":
                    return {"challenge": data.get("challenge")}
                
                # 2. Event Handling (v2.0)
                header = data.get("header", {})
                event = data.get("event", {})
                event_type = header.get("event_type")

                if event_type == "im.message.receive_v1":
                    message = event.get("message", {})
                    if message.get("message_type") == "text":
                        # Content is JSON string in Feishu
                        content_json = json.loads(message.get("content", "{}"))
                        text = content_json.get("text", "").strip()
                        
                        sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id")
                        chat_id = message.get("chat_id")

                        if text and sender_id and chat_id:
                            gw_msg = GatewayMessage(
                                sender_id=sender_id,
                                channel="feishu",
                                channel_id=chat_id,
                                content=text
                            )
                            
                            if self._message_handler:
                                asyncio.create_task(self._handle_and_reply(gw_msg, message.get("message_id")))

                return {"status": "ok"}
            except Exception:
                logger.exception("feishu_webhook_error")
                return Response(status_code=500)

    async def _handle_and_reply(self, gw_msg: GatewayMessage, reply_to_id: str) -> None:
        """Process message and send reply."""
        if not self._message_handler:
            return
        try:
            response = await self._message_handler(gw_msg)
            if response:
                await self.send_message(gw_msg.channel_id, response, reply_to_id=reply_to_id)
        except Exception:
            logger.exception("feishu_reply_error", sender_id=gw_msg.sender_id)

    async def start(self) -> None:
        logger.info("feishu_channel_started", app_id=self.app_id)

    async def stop(self) -> None:
        logger.info("feishu_channel_stopped")

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
        reply_to_id: str | None = None
    ) -> None:
        """Send a message to a Feishu chat via OpenAPI."""
        token = await self._get_tenant_token()
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        
        params = {"receive_id_type": "chat_id"}
        if reply_to_id:
            url = f"{url}/{reply_to_id}/reply"
            params = {}

        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            for chunk in chunk_text(content, _FEISHU_MAX_MESSAGE_LEN):
                body = {
                    "msg_type": "text",
                    "content": json.dumps({"text": chunk})
                }
                if not reply_to_id:
                    body["receive_id"] = channel_id

                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=body, headers=headers, params=params)
                    if resp.status_code != 200:
                        logger.error("feishu_send_failed_api", status=resp.status_code, body=resp.text)
        except Exception:
            logger.exception("feishu_send_failed", channel_id=channel_id)
