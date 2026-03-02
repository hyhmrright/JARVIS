import abc
import asyncio
import hashlib
import imaplib
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


class IMAPEmailProcessor(TriggerProcessor):
    """Fires when new unread emails arrive."""

    async def should_fire(self, metadata: dict[str, Any]) -> bool:
        host = metadata.get("imap_host")
        user = metadata.get("imap_user")
        password = metadata.get("imap_password")
        if not all([host, user, password]):
            return False

        last_uid = metadata.get("last_uid", 0)
        try:

            def check_emails():
                with imaplib.IMAP4_SSL(host) as mail:
                    mail.login(user, password)
                    mail.select("inbox")
                    status, messages = mail.search(None, "UNSEEN")
                    if status != "OK":
                        return None
                    msg_ids = messages[0].split()
                    if not msg_ids:
                        return None
                    latest_uid = int(msg_ids[-1])
                    if latest_uid > last_uid:
                        return latest_uid
                return None

            new_latest_uid = await asyncio.to_thread(check_emails)
            if new_latest_uid:
                metadata["last_uid"] = new_latest_uid
                return True
        except Exception:
            logger.exception("email_trigger_check_failed", user=user)

        return False


_PROCESSORS: dict[str, TriggerProcessor] = {
    "web_watcher": WebWatcherProcessor(),
    "email": IMAPEmailProcessor(),
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
