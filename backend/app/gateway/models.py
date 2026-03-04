from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GatewayMessage:
    """A normalized message from any channel."""

    sender_id: str
    channel: str  # "web" | "telegram" | "discord" | "wechat"
    channel_id: str  # channel-specific chat/group ID
    content: str
    attachments: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


MessageHandler = Callable[[GatewayMessage], Awaitable[str | None]]


class ChannelAdapter(ABC):
    """Abstract base class for channel-specific adapters."""

    channel_name: str

    def __init__(self) -> None:
        self._message_handler: MessageHandler | None = None

    @abstractmethod
    async def start(self) -> None:
        """Start the channel adapter (connect, poll, etc.)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel adapter and release resources."""
        ...

    @abstractmethod
    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[Any] | None = None,
    ) -> None:
        """Send a message back to the channel."""
        ...

    def set_message_handler(self, handler: MessageHandler) -> None:
        """Register the callback invoked when an inbound message arrives."""
        self._message_handler = handler


def chunk_text(text: str, max_length: int) -> list[str]:
    """Split *text* into chunks of at most *max_length* characters."""
    return [
        text[offset : offset + max_length] for offset in range(0, len(text), max_length)
    ]
