import structlog

from app.channels.base import BaseChannelAdapter

logger = structlog.get_logger(__name__)


class ChannelRegistry:
    """Manages active messaging channel adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, BaseChannelAdapter] = {}

    def register(self, adapter: BaseChannelAdapter) -> None:
        """Register a new channel adapter."""
        if adapter.channel_name in self._adapters:
            logger.warning("channel_already_registered", channel=adapter.channel_name)
        self._adapters[adapter.channel_name] = adapter
        logger.info("channel_registered", channel=adapter.channel_name)

    def get(self, channel_name: str) -> BaseChannelAdapter | None:
        """Get a registered adapter by its channel name."""
        return self._adapters.get(channel_name)

    def all_channels(self) -> list[str]:
        """Return a list of all registered channel names."""
        return list(self._adapters.keys())

    async def start_all(self) -> None:
        """Start all registered channel adapters."""
        for adapter in self._adapters.values():
            await adapter.start()

    async def stop_all(self) -> None:
        """Stop all registered channel adapters."""
        for adapter in self._adapters.values():
            await adapter.stop()
