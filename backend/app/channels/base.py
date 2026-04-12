from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class GatewayMessage:
    """标准化的全渠道消息。"""

    sender_id: str
    channel: str  # "web" | "telegram" | "discord" | "wechat" | "feishu"
    channel_id: str  # 渠道特定的聊天/群组 ID
    content: str
    attachments: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


MessageHandler = Callable[[GatewayMessage], Awaitable[str | None]]


class BaseChannelAdapter(ABC):
    """渠道适配器的抽象基类。"""

    channel_name: str
    # 默认分块长度（可由子类覆盖）
    max_message_length: int = 2000

    def __init__(self) -> None:
        self._message_handler: MessageHandler | None = None

    @abstractmethod
    async def start(self) -> None:
        """启动适配器（连接、轮询等）。"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """停止适配器并释放资源。"""
        ...

    @abstractmethod
    async def _send_raw_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """执行具体的发送逻辑（由子类实现）。"""
        ...

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
        reply_to_id: str | None = None,
    ) -> None:
        """发送消息，自动处理分块和错误记录。"""
        if not content and not attachments:
            return

        chunks = chunk_text(content, self.max_message_length) if content else [""]

        # If reply_to_id is provided, pass it in attachments as the first element
        # (This convention is used by some adapters like Feishu)
        full_attachments = list(attachments) if attachments else []
        if reply_to_id:
            full_attachments.insert(0, reply_to_id)

        for i, chunk in enumerate(chunks):
            try:
                # 仅在最后一块附带附件（如果适配器支持）
                current_attachments = full_attachments if i == len(chunks) - 1 else None
                await self._send_raw_message(channel_id, chunk, current_attachments)
            except Exception:
                logger.exception(
                    "channel_send_failed",
                    channel=self.channel_name,
                    channel_id=channel_id,
                    chunk_index=i,
                )
                raise

    def set_message_handler(self, handler: MessageHandler) -> None:
        """注册当收到入站消息时调用的回调函数。"""
        self._message_handler = handler


def chunk_text(text: str, max_length: int) -> list[str]:
    """将文本切分为最大长度为 max_length 的块。"""
    if not text:
        return []
    return [
        text[offset : offset + max_length] for offset in range(0, len(text), max_length)
    ]
