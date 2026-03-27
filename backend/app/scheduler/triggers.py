"""Trigger processors for proactive monitoring.

Each processor implements should_fire(metadata) -> TriggerResult.
Metadata dict is mutated in-place to persist state (e.g., last_hash).
"""

import email as email_lib
import email.message
import hashlib
import imaplib
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Literal

import httpx
import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.llm_factory import get_llm_with_fallback
from app.core.security import fernet_decrypt
from app.scheduler.fetch import fetch_page_content
from app.scheduler.prompts import (
    SEMANTIC_WATCHER_SYSTEM_PROMPT,
    SEMANTIC_WATCHER_USER_PROMPT,
)
from app.scheduler.trigger_result import TriggerResult

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Structured output schema for SemanticWatcher
# ---------------------------------------------------------------------------


class SemanticAnalysisResult(BaseModel):
    changed: bool
    summary: str
    confidence: Literal["high", "medium", "low"]


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class TriggerProcessor(ABC):
    @abstractmethod
    async def should_fire(self, metadata: dict) -> TriggerResult:
        """Evaluate trigger condition. Mutates metadata in-place to persist state."""


# ---------------------------------------------------------------------------
# Web Watcher (hash-based)
# ---------------------------------------------------------------------------


class WebWatcherProcessor(TriggerProcessor):
    async def should_fire(self, metadata: dict) -> TriggerResult:
        url: str = metadata.get("url", "")
        http_headers: dict = metadata.get("http_headers") or {}

        try:
            text = await fetch_page_content(url, http_headers=http_headers)
        except (ValueError, httpx.HTTPError) as exc:
            logger.warning("web_watcher_fetch_failed", url=url, error=str(exc))
            return TriggerResult(fired=False, reason="error")

        new_hash = hashlib.md5(text.encode()).hexdigest()
        last_hash = metadata.get("last_hash")

        if last_hash is None:
            metadata["last_hash"] = new_hash
            return TriggerResult(fired=False, reason="first_run_initialized")

        if new_hash == last_hash:
            return TriggerResult(fired=False, reason="content_hash_unchanged")

        metadata["last_hash"] = new_hash
        return TriggerResult(
            fired=True,
            reason="fired",
            trigger_ctx={
                "trigger_type": "web_watcher",
                "url": url,
                "detected_at": datetime.now(tz=UTC).isoformat(),
                "changed_summary": "网页内容已变化",
                "confidence": "high",
            },
        )


# ---------------------------------------------------------------------------
# Semantic Watcher (LLM-based)
# ---------------------------------------------------------------------------


class SemanticWatcherProcessor(TriggerProcessor):
    async def should_fire(self, metadata: dict) -> TriggerResult:
        url: str = metadata.get("url", "")
        target: str = metadata.get("target", "内容变化")
        http_headers: dict = metadata.get("http_headers") or {}
        fire_on_init: bool = metadata.get("fire_on_init", False)

        try:
            text = await fetch_page_content(url, http_headers=http_headers)
        except (ValueError, httpx.HTTPError) as exc:
            logger.warning("semantic_watcher_fetch_failed", url=url, error=str(exc))
            return TriggerResult(fired=False, reason="error")

        new_hash = hashlib.md5(text.encode()).hexdigest()
        last_summary: str | None = metadata.get("last_semantic_summary")

        # --- First run: no previous state ---
        if last_summary is None:
            metadata["content_hash"] = new_hash
            metadata["last_semantic_summary"] = text[:200]
            if fire_on_init:
                return TriggerResult(
                    fired=True,
                    reason="fired",
                    trigger_ctx={
                        "trigger_type": "semantic_watcher",
                        "url": url,
                        "target": target,
                        "detected_at": datetime.now(tz=UTC).isoformat(),
                        "changed_summary": "已初始化监控",
                        "confidence": "high",
                    },
                )
            return TriggerResult(fired=False, reason="first_run_initialized")

        # --- Content hash pre-check: skip LLM if unchanged ---
        if new_hash == metadata.get("content_hash"):
            return TriggerResult(fired=False, reason="content_hash_unchanged")

        # --- LLM semantic analysis ---
        analysis = await self._analyze(target, last_summary, text)
        if analysis is None:
            return TriggerResult(fired=False, reason="llm_parse_error")

        metadata["content_hash"] = new_hash
        if analysis.changed:
            metadata["last_semantic_summary"] = analysis.summary
            return TriggerResult(
                fired=True,
                reason="fired",
                trigger_ctx={
                    "trigger_type": "semantic_watcher",
                    "url": url,
                    "target": target,
                    "detected_at": datetime.now(tz=UTC).isoformat(),
                    "changed_summary": analysis.summary,
                    "confidence": analysis.confidence,
                },
            )

        return TriggerResult(fired=False, reason="skipped")

    async def _analyze(
        self, target: str, last_summary: str, new_content: str
    ) -> SemanticAnalysisResult | None:
        provider = "deepseek"
        model = "deepseek-chat"
        api_key = settings.deepseek_api_key
        if not api_key and settings.openai_api_key:
            provider = "openai"
            model = "gpt-4o-mini"
            api_key = settings.openai_api_key
        if not api_key:
            logger.warning("semantic_watcher_no_api_key")
            return None

        llm = get_llm_with_fallback(provider, model, api_key)
        messages = [
            SystemMessage(content=SEMANTIC_WATCHER_SYSTEM_PROMPT),
            HumanMessage(
                content=SEMANTIC_WATCHER_USER_PROMPT.format(
                    target=target,
                    last_summary=last_summary,
                    new_content=new_content,
                )
            ),
        ]

        # Try structured output first; fall back to JSON parsing
        try:
            structured_llm = llm.with_structured_output(SemanticAnalysisResult)
            return await structured_llm.ainvoke(messages)
        except Exception as e:  # noqa: BLE001
            logger.debug("semantic_watcher_structured_output_failed", error=str(e))

        try:
            raw = await llm.ainvoke(messages)
            data = json.loads(str(raw.content))
            return SemanticAnalysisResult(**data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("semantic_watcher_llm_parse_error", error=str(exc))
            return None
        except Exception:
            logger.error(
                "semantic_watcher_unexpected_error",
                exc_info=True,
            )
            return None


# ---------------------------------------------------------------------------
# IMAP Email Processor
# ---------------------------------------------------------------------------


def _fetch_emails_since_uid(
    conn: imaplib.IMAP4 | imaplib.IMAP4_SSL,
    last_uid: int,
    max_emails: int = 10,
) -> tuple[list[email.message.Message], list[bytes]]:
    """Return (messages, uid_bytes) for UIDs > last_uid, capped at max_emails."""
    _, data = conn.uid("search", "UTF-8", f"UID {last_uid + 1}:*")
    raw_uids: list[bytes] = data[0].split() if data[0] else []
    uids = raw_uids[-max_emails:]
    messages = []
    for uid in uids:
        uid_str = uid.decode() if isinstance(uid, bytes) else uid
        _, raw = conn.uid("fetch", uid_str, "(RFC822)")
        if raw and raw[0]:
            messages.append(email_lib.message_from_bytes(raw[0][1]))
    return messages, uids


def _extract_body_snippet(msg: email.message.Message, max_chars: int = 500) -> str:
    """Extract plaintext snippet from email MIME parts."""
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes):
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace").strip()[:max_chars]
    return ""


class IMAPEmailProcessor(TriggerProcessor):
    async def should_fire(self, metadata: dict) -> TriggerResult:
        import asyncio

        return await asyncio.to_thread(self._check_imap, metadata)

    def _check_imap(self, metadata: dict) -> TriggerResult:
        host: str = metadata.get("imap_host", "")
        port: int = metadata.get("imap_port", 993)
        user: str = metadata.get("imap_user", "")
        encrypted_password: str = metadata.get("imap_password", "")
        folder: str = metadata.get("imap_folder", "INBOX")
        last_uid: int = metadata.get("last_uid", 0)

        try:
            password = fernet_decrypt(encrypted_password)
        except Exception as exc:
            logger.error("imap_decrypt_failed", error=str(exc))
            return TriggerResult(fired=False, reason="error")

        try:
            if port == 993:
                conn: imaplib.IMAP4 | imaplib.IMAP4_SSL = imaplib.IMAP4_SSL(host, port)
            else:
                conn = imaplib.IMAP4(host, port)
                conn.starttls()

            conn.login(user, password)
            conn.select(folder)

            messages, new_uids = _fetch_emails_since_uid(conn, last_uid)
            conn.logout()
        except imaplib.IMAP4.error as exc:
            logger.warning("imap_check_failed", error=str(exc))
            return TriggerResult(fired=False, reason="error")

        if not new_uids:
            return TriggerResult(fired=False, reason="no_new_emails")

        metadata["last_uid"] = max(
            int(uid.decode() if isinstance(uid, bytes) else uid) for uid in new_uids
        )

        parsed_emails = [
            {
                "from": msg.get("From", ""),
                "subject": msg.get("Subject", ""),
                "date": msg.get("Date", ""),
                "snippet": _extract_body_snippet(msg),
            }
            for msg in messages
        ]

        return TriggerResult(
            fired=True,
            reason="fired",
            trigger_ctx={
                "trigger_type": "email",
                "detected_at": datetime.now(tz=UTC).isoformat(),
                "new_email_count": len(new_uids),
                "emails": parsed_emails,
            },
        )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


async def evaluate_trigger(trigger_type: str, metadata: dict) -> TriggerResult:
    """Route to the appropriate processor and return a TriggerResult."""
    match trigger_type:
        case "cron":
            return TriggerResult(fired=True, reason="fired")
        case "web_watcher":
            return await WebWatcherProcessor().should_fire(metadata)
        case "semantic_watcher":
            return await SemanticWatcherProcessor().should_fire(metadata)
        case "email":
            return await IMAPEmailProcessor().should_fire(metadata)
        case _:
            logger.warning("unknown_trigger_type", trigger_type=trigger_type)
            return TriggerResult(fired=True, reason="fired")
