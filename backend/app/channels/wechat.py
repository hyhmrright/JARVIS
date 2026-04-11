import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, Response
from wechatpy import WeChatClient, parse_message
from wechatpy.crypto import WeChatCrypto
from wechatpy.exceptions import InvalidAppIdException, InvalidSignatureException

from app.channels.base import BaseChannelAdapter, GatewayMessage

logger = structlog.get_logger(__name__)


class WeChatChannel(BaseChannelAdapter):
    """使用 wechatpy 的微信公众号渠道适配器。"""

    channel_name = "wechat"
    # 微信对文本长度有限制，安全起见设为 2000 字符
    max_message_length = 2000

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
        self.crypto = (
            WeChatCrypto(self._token, self._encoding_aes_key, self._app_id)
            if self._encoding_aes_key
            else None
        )

        self.router = APIRouter()
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.router.get("/")
        async def wechat_verify(
            signature: str = "",
            timestamp: str = "",
            nonce: str = "",
            echostr: str = "",
        ) -> Response:
            """验证微信服务器。"""
            from wechatpy.utils import check_signature

            try:
                check_signature(self._token, signature, timestamp, nonce)
            except InvalidSignatureException:
                raise HTTPException(
                    status_code=403, detail="Invalid signature"
                ) from None  # noqa: E501
            return Response(content=echostr)

        @self.router.post("/")
        async def wechat_receive(
            request: Request,
            signature: str = "",
            timestamp: str = "",
            nonce: str = "",
            msg_signature: str = "",
            encrypt_type: str = "raw",
        ) -> Response:
            """从微信接收消息。"""
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
                raise HTTPException(
                    status_code=403, detail="Invalid signature or app id"
                ) from None  # noqa: E501
            except Exception as e:
                logger.error("wechat_parse_error", error=str(e))
                return Response(content="success")

            if msg.type == "text":
                gw_msg = GatewayMessage(
                    sender_id=msg.source,
                    channel="wechat",
                    channel_id=msg.target,  # 通常是公众号 ID
                    content=msg.content,
                )
                if self._message_handler:
                    # 在后台运行任务，立即返回 EmptyReply（成功）
                    asyncio.create_task(self._process_message(gw_msg))

            # 目前立即返回成功响应，以免微信超时
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

    async def _send_raw_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """使用微信客服 API 发送消息。"""
        try:
            # 由于 wechatpy 客户端是同步的，使用 asyncio.to_thread
            await asyncio.to_thread(
                self.client.message.send_text, user_id=channel_id, content=content
            )
        except Exception:
            logger.exception("wechat_send_failed", channel_id=channel_id)
