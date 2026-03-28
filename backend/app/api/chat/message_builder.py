"""Message construction helpers: history traversal, LangChain message building,
and memory injection."""

import json
import uuid
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, UserMemory

logger = structlog.get_logger(__name__)

_ROLE_TO_MESSAGE = {
    "human": HumanMessage,
    "ai": AIMessage,
    "tool": ToolMessage,
    "system": SystemMessage,
}

_MEMORY_PROMPT_LIMIT = 100
_MEMORY_CHAR_LIMIT = 8000


async def build_memory_message(
    db: AsyncSession, user_id: uuid.UUID
) -> SystemMessage | None:
    """Load user memories and return a SystemMessage for prompt injection, or None."""
    rows = await db.scalars(
        select(UserMemory)
        .where(UserMemory.user_id == user_id)
        .order_by(UserMemory.category, UserMemory.key)
        .limit(_MEMORY_PROMPT_LIMIT)
    )
    memories = list(rows.all())

    lines: list[str] = []
    total_chars = 0
    for m in reversed(memories):
        line = f"- [{m.category}] {m.key}: {m.value}"
        if total_chars + len(line) > _MEMORY_CHAR_LIMIT:
            break
        lines.append(line)
        total_chars += len(line)

    if not lines:
        return None

    block = "## 用户个人记忆（跨对话持久化）\n" + "\n".join(lines)
    return SystemMessage(content=block)


def walk_message_chain(
    msg_dict: dict,
    start_id: uuid.UUID | None,
    max_depth: int = 500,
) -> list:
    """Trace parent_id links from start_id, returning messages chronologically."""
    history: list = []
    current_id = start_id
    depth = 0
    while current_id and current_id in msg_dict and depth < max_depth:
        history.append(msg_dict[current_id])
        current_id = msg_dict[current_id].parent_id
        depth += 1
    history.reverse()
    return history


def build_langchain_messages(history: list) -> list:
    """Convert a sequence of DB Message objects into LangChain message types."""
    lc_messages = []
    for msg in history:
        message_class = _ROLE_TO_MESSAGE.get(msg.role)
        if not message_class:
            logger.debug(
                "chat_history_message_skipped",
                role=msg.role,
                msg_id=str(msg.id),
            )
            continue
        kwargs = _build_message_kwargs(msg)
        lc_messages.append(message_class(**kwargs))
    return lc_messages


def _build_message_kwargs(msg: Message) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"content": msg.content}

    if msg.role == "human" and msg.image_urls:
        content_blocks: list[dict[str, Any]] = [{"type": "text", "text": msg.content}]
        for url in msg.image_urls:
            content_blocks.append({"type": "image_url", "image_url": {"url": url}})
        kwargs["content"] = content_blocks

    if msg.role == "ai" and msg.tool_calls:
        kwargs["tool_calls"] = msg.tool_calls

    if msg.role == "tool":
        kwargs.update(_build_tool_message_kwargs(msg))

    return kwargs


def _build_tool_message_kwargs(msg: Message) -> dict[str, Any]:
    tool_payload: dict[str, Any] | None = None
    try:
        parsed = json.loads(msg.content)
        if isinstance(parsed, dict):
            tool_payload = parsed
    except json.JSONDecodeError:
        tool_payload = None

    if not tool_payload:
        return {"tool_call_id": str(msg.id)}

    kwargs: dict[str, Any] = {
        "content": str(tool_payload.get("content", msg.content)),
        "tool_call_id": str(tool_payload.get("tool_call_id") or msg.id),
    }
    if tool_payload.get("name"):
        kwargs["name"] = str(tool_payload["name"])
    return kwargs
