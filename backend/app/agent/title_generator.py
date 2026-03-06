"""Generates a short conversation title from the first exchange."""

from __future__ import annotations

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm import get_llm

logger = structlog.get_logger(__name__)

_TITLE_PROMPT = """\
Based on the following conversation exchange, generate a concise title \
in the same language as the user's message.
The title must be <= 10 characters (Chinese) or <= 6 words (English).
Reply with ONLY the title text. No punctuation, no quotes."""


async def generate_title(
    *,
    user_message: str,
    ai_reply: str,
    provider: str,
    model: str,
    api_key: str,
) -> str | None:
    """Generate a short conversation title. Returns None on any error."""
    try:
        llm = get_llm(provider, model, api_key)
        context = f"User: {user_message[:200]}\nAssistant: {ai_reply[:200]}"
        response = await llm.ainvoke(
            [
                SystemMessage(content=_TITLE_PROMPT),
                HumanMessage(content=context),
            ]
        )
        title = response.content
        return (title if isinstance(title, str) else "").strip()[:50] or None
    except Exception:
        logger.warning("title_generation_failed", exc_info=True)
        return None
