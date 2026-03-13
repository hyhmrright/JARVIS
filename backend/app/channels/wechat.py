import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, Request, Response, HTTPException
from wechatpy import WeChatClient, parse_message
from wechatpy.crypto import WeChatCrypto
from wechatpy.exceptions import InvalidSignatureException, InvalidAppIdException
from wechatpy.replies import EmptyReply

from app.channels.base import BaseChannelAdapter, GatewayMessage, chunk_text
from app.core.config import settings

logger = structlog.get_logger(__name__)

# WeChat limits text length, safe to break at 2000 chars like discord
_WECHAT_MAX_MESSAGE_LEN = 2000

class WeChatChannel(BaseChannelAdapter):
    """WeChat Official Account channel adapter using wechatpy."""

    channel_name = "wechat"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        token: str,
        encoding_aes_key: str,
    ) -> None:
        super().__init__()
        self._app_id = app_id
        self._app_secret = app_secret
        self._token = token
        self._encoding_aes_key = encoding_aes_key

        self.client = WeChatClient(self._app_id, self._app_secret)
        self.crypto = WeChatCrypto(self._token, self._encoding_aes_key, self._app_id) if self._encoding_aes_key else None
        
        self.router = APIRouter()
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.router.get("/")
        async def wechat_verify(
            signature: str = "",
            timestamp: str = "",
            nonce: str = "",
            echostr: str = "",
        ):
            """Verify WeChat server."""
            from wechatpy.utils import check_signature
            try:
                check_signature(self._token, signature, timestamp, nonce)
            except InvalidSignatureException:
                raise HTTPException(status_code=403, detail="Invalid signature")
            return Response(content=echostr)

        @self.router.post("/")
        async def wechat_receive(
            request: Request,
            signature: str = "",
            timestamp: str = "",
            nonce: str = "",
            msg_signature: str = "",
            encrypt_type: str = "raw",
        ):
            """Receive messages from WeChat."""
            body = await request.body()
            
            try:
                if encrypt_type == "aes" and self.crypto:
                    decrypted_xml = self.crypto.decrypt_message(
                        body, msg_signature, timestamp, nonce
                    )
                    msg = parse_message(decrypted_xml)
                else:
                    from wechatpy.utils import check_signature
                    check_signature(self._token, signature, timestamp, nonce)
                    msg = parse_message(body)
            except (InvalidSignatureException, InvalidAppIdException):
                raise HTTPException(status_code=403, detail="Invalid signature or app id")
            except Exception as e:
                logger.error("wechat_parse_error", error=str(e))
                return Response(content="success")
            
            if msg.type == "text":
                gw_msg = GatewayMessage(
                    sender_id=msg.source,
                    channel="wechat",
                    channel_id=msg.target, # Usually the official account ID
                    content=msg.content,
                )
                if self._message_handler:
                    # Run background task, return EmptyReply immediately (success)
                    asyncio.create_task(self._process_message(gw_msg))
            
            # For now, immediately return an empty response so wechat doesn't timeout
            return Response(content="success")

    async def _process_message(self, gw_msg: GatewayMessage) -> None:
        if not self._message_handler:
            return
            
        try:
            response = await self._message_handler(gw_msg)
        except Exception:
            logger.exception("wechat_handler_error", sender_id=gw_msg.sender_id)
            return

        if response:
            await self.send_message(gw_msg.sender_id, response)

    async def start(self) -> None:
        logger.info("wechat_channel_started")

    async def stop(self) -> None:
        logger.info("wechat_channel_stopped")

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """Send a message using WeChat Customer Service API."""
        try:
            for chunk in chunk_text(content, _WECHAT_MAX_MESSAGE_LEN):
                # Using asyncio.to_thread because wechatpy client is synchronous
                await asyncio.to_thread(
                    self.client.message.send_text,
                    user_id=channel_id,
                    content=chunk
                )
        except Exception:
            logger.exception("wechat_send_failed", channel_id=channel_id)
