import abc
import asyncio
import hashlib
import imaplib
from typing import Any

import httpx
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm import get_llm_with_fallback
from app.core.config import settings
from app.core.security import fernet_decrypt
from app.scheduler.prompts import (
    SEMANTIC_WATCHER_SYSTEM_PROMPT,
    SEMANTIC_WATCHER_USER_PROMPT,
)

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


class SemanticWatcherProcessor(TriggerProcessor):
    """Fires when a webpage's content has a significant semantic change."""

    def _truncate_content(self, text: str, max_chars: int = 12000) -> str:
        """Truncate text to fit within typical context windows with safety margin."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n...[内容已截断]"

    async def should_fire(self, metadata: dict[str, Any]) -> bool:
        url = metadata.get("url")
        if not url:
            return False

        last_summary = metadata.get("last_semantic_summary", "")
        target = metadata.get("target", "核心主旨、事实或重要实体变动")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                new_content = self._truncate_content(response.text)

            # Use server-level LLM keys for semantic checking.
            # Priority: deepseek > openai (whichever has a key configured).
            if settings.deepseek_api_key:
                provider = "deepseek"
                model = "deepseek-chat"
                api_key = settings.deepseek_api_key
            elif settings.openai_api_key:
                provider = "openai"
                model = "gpt-4o-mini"
                api_key = settings.openai_api_key
            else:
                logger.error("semantic_watcher_no_api_key")
                return False

            llm = get_llm_with_fallback(provider, model, api_key)

            prompt = SEMANTIC_WATCHER_USER_PROMPT.format(
                target=target,
                last_summary=last_summary or "尚无记录",
                new_content=new_content,
            )
            messages = [
                SystemMessage(content=SEMANTIC_WATCHER_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]

            res = await llm.ainvoke(messages)
            reply = str(res.content).strip()

            if reply.startswith("语义已变动："):
                new_summary = reply[len("语义已变动：") :].strip()
                metadata["last_semantic_summary"] = new_summary
                return True

            # If no record exists, store initial summary but don't fire yet
            if not last_summary:
                # First run, initialize summary but don't fire
                metadata["last_semantic_summary"] = "已初始化。后续将监控：" + target
                return False

        except Exception:
            logger.exception("semantic_watcher_check_failed", url=url)

        return False


class IMAPEmailProcessor(TriggerProcessor):
    """Fires when new unread emails arrive."""

    async def should_fire(self, metadata: dict[str, Any]) -> bool:
        host = metadata.get("imap_host")
        user = metadata.get("imap_user")
        password_encrypted = metadata.get("imap_password")
        if not all([host, user, password_encrypted]):
            return False
        try:
            password = fernet_decrypt(str(password_encrypted))
        except Exception:
            logger.error("imap_password_decrypt_failed", user=user)
            return False

        last_uid = metadata.get("last_uid", 0)
        try:

            def check_emails() -> int | None:
                with imaplib.IMAP4_SSL(str(host)) as mail:
                    mail.login(str(user), str(password))
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
    "semantic_watcher": SemanticWatcherProcessor(),
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
