import structlog

from app.gateway.models import ChannelAdapter

logger = structlog.get_logger(__name__)


class ChannelRegistry:
    """Manages registered channel adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, ChannelAdapter] = {}

    def register(self, adapter: ChannelAdapter) -> None:
        """Register a channel adapter by its channel_name."""
        name = adapter.channel_name
        if name in self._adapters:
            logger.warning("channel_already_registered", channel=name)
        self._adapters[name] = adapter
        logger.info("channel_registered", channel=name)

    def get(self, channel_name: str) -> ChannelAdapter | None:
        """Return the adapter for channel_name, or None if not registered."""
        return self._adapters.get(channel_name)

    def all_channels(self) -> list[str]:
        """Return names of all registered channels."""
        return list(self._adapters.keys())

    async def start_all(self) -> None:
        """Start every registered adapter."""
        for name, adapter in self._adapters.items():
            try:
                logger.info("starting_channel", channel=name)
                await adapter.start()
            except Exception:
                logger.exception("channel_start_failed", channel=name)

    async def stop_all(self) -> None:
        """Stop every registered adapter."""
        for name, adapter in self._adapters.items():
            try:
                logger.info("stopping_channel", channel=name)
                await adapter.stop()
            except Exception:
                logger.exception("channel_stop_failed", channel=name)
