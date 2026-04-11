import re
import uuid
from collections.abc import Callable

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation
from app.gateway.channel_registry import ChannelRegistry
from app.gateway.models import GatewayMessage
from app.gateway.pairing import (
    PAIRING_INVALID,
    PAIRING_PROMPT,
    PAIRING_SUCCESS,
    PairingManager,
)
from app.gateway.session_manager import SessionManager
from app.services.agent_engine import AgentEngine

logger = structlog.get_logger(__name__)

_CODE_RE = re.compile(r"^\s*(\d{6})\s*$")


class GatewayRouter:
    """路由来自任何渠道的消息到适当的 Agent 会话。"""

    def __init__(
        self,
        registry: ChannelRegistry,
        session_manager: SessionManager,
        pairing_manager: PairingManager | None = None,
        *,
        db_session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._registry = registry
        self._session_manager = session_manager
        self._pairing_manager = pairing_manager
        self._db_session_factory = db_session_factory

    async def handle_message(self, msg: GatewayMessage) -> str:
        """处理入站 GatewayMessage 并返回 Agent 回复。"""
        adapter = self._registry.get(msg.channel)
        if adapter is None:
            raise ValueError(f"Unknown channel: {msg.channel!r}")

        session = await self._session_manager.get_or_create_session(
            sender_id=msg.sender_id, channel=msg.channel
        )
        user_id: str | None = session.get("user_id")

        if user_id is None:
            return await self._handle_unauthenticated(msg)

        if self._db_session_factory is None:
            from app.db.session import AsyncSessionLocal

            self._db_session_factory = AsyncSessionLocal

        assert self._db_session_factory is not None

        try:
            async with self._db_session_factory() as db:
                engine = AgentEngine(db)
                conv_id_str = session.get("conversation_id")
                conv_id = uuid.UUID(conv_id_str) if conv_id_str else None

                reply = await engine.run_blocking(
                    user_id=uuid.UUID(user_id),
                    content=msg.content,
                    conversation_id=conv_id,
                    channel=msg.channel,
                )

                # 更新会话映射
                if not conv_id_str:
                    conv = await db.scalar(
                        select(Conversation)
                        .where(Conversation.user_id == uuid.UUID(user_id))
                        .order_by(Conversation.created_at.desc())
                    )
                    if conv:
                        await self._session_manager.update_session(
                            sender_id=msg.sender_id,
                            channel=msg.channel,
                            conversation_id=str(conv.id),
                        )
                return reply
        except Exception:
            logger.exception(
                "gateway_handle_error", user_id=user_id, channel=msg.channel
            )
            return "抱歉，处理您的请求时出错。请稍后再试。"

    async def _handle_unauthenticated(self, msg: GatewayMessage) -> str:
        """处理未关联账号的消息。"""
        logger.warning(
            "gateway_unauthenticated", channel=msg.channel, sender_id=msg.sender_id
        )

        match = _CODE_RE.match(msg.content)
        if match and self._pairing_manager is not None:
            code = match.group(1)
            linked_user_id = await self._pairing_manager.validate_code(code)
            if linked_user_id is not None:
                await self._session_manager.link_user(
                    sender_id=msg.sender_id,
                    channel=msg.channel,
                    user_id=linked_user_id,
                )
                logger.info(
                    "gateway_pairing_success",
                    channel=msg.channel,
                    user_id=linked_user_id,
                )
                return PAIRING_SUCCESS
            return PAIRING_INVALID

        return PAIRING_PROMPT
