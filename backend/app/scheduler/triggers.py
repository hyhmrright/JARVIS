import abc
import hashlib
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class TriggerProcessor(abc.ABC):
    """Base class for proactive triggers."""

    @abc.abstractmethod
    async def should_fire(self, metadata: dict[str, Any]) -> bool:
        """Return True if the conditions for firing are met."""


class WebWatcherProcessor(TriggerProcessor):
    """Fires when a specific webpage's content changes."""

    async def should_fire(self, metadata: dict[str, Any]) -> bool:
        url = metadata.get("url")
        if not url:
            return False

        last_hash = metadata.get("last_hash")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                content = response.text
                current_hash = hashlib.md5(content.encode()).hexdigest()

                if current_hash != last_hash:
                    metadata["last_hash"] = current_hash
                    return True
        except Exception:
            logger.exception("web_watcher_check_failed", url=url)

        return False


_PROCESSORS: dict[str, TriggerProcessor] = {
    "web_watcher": WebWatcherProcessor(),
}


async def evaluate_trigger(trigger_type: str, metadata: dict[str, Any]) -> bool:
    """Evaluate a proactive trigger and update metadata in-place if fired."""
    if trigger_type == "cron":
        return True

    processor = _PROCESSORS.get(trigger_type)
    if not processor:
        logger.warning("unknown_trigger_type", type=trigger_type)
        return True  # Fallback to fire anyway

    return await processor.should_fire(metadata)
