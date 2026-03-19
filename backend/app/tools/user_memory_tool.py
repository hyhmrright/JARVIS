"""Persistent user memory tools — store and recall facts across conversations."""

from __future__ import annotations

import uuid

import structlog
from langchain_core.tools import BaseTool, tool
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import UserMemory
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)

_VALID_CATEGORIES = frozenset({"preference", "fact", "reminder", "general"})
_MAX_VALUE_LEN = 2_000
_RECALL_LIMIT = 100


def create_user_memory_tools(user_id: str) -> list[BaseTool]:
    """Return [remember, recall] tools closed over the given user."""
    uid = uuid.UUID(user_id)

    @tool
    async def remember(key: str, value: str, category: str = "general") -> str:
        """Store or update a persistent fact about the user.

        Use this whenever the user shares information they want you to remember,
        such as preferences, personal details, or ongoing reminders.  Stored
        memories are automatically injected into future conversations.

        Args:
            key: Short snake_case identifier, e.g. "preferred_language" or "name".
            value: The value to store, e.g. "Python" or "Alice".
            category: One of "preference", "fact", "reminder", "general".
        """
        if not key.strip():
            return "Key must not be empty or whitespace."
        if category not in _VALID_CATEGORIES:
            return (
                f"Invalid category '{category}'. "
                f"Must be one of: {', '.join(sorted(_VALID_CATEGORIES))}"
            )
        if len(value) > _MAX_VALUE_LEN:
            return f"Value too long ({len(value)} chars). Maximum is {_MAX_VALUE_LEN}."
        async with AsyncSessionLocal() as db:
            stmt = (
                pg_insert(UserMemory)
                .values(user_id=uid, key=key, value=value, category=category)
                .on_conflict_do_update(
                    constraint="uq_user_memories_user_key",
                    set_={
                        "value": value,
                        "category": category,
                        "updated_at": func.now(),
                    },
                )
            )
            await db.execute(stmt)
            await db.commit()
        logger.info("user_memory_saved", user_id=user_id, key=key, category=category)
        return f"Memory saved: {key} = {value!r} (category: {category})"

    @tool
    async def recall(query: str = "") -> str:
        """Retrieve facts from persistent memory.

        Returns stored memories, optionally filtered by a substring query against
        the key or value.  Call this when the user asks what you remember about
        them, or when context from past conversations is needed.

        Args:
            query: Optional filter. Leave empty to list all memories.
        """
        async with AsyncSessionLocal() as db:
            base = select(UserMemory).where(UserMemory.user_id == uid)
            if query:
                escaped = (
                    query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                )
                pattern = f"%{escaped}%"
                base = base.where(
                    or_(
                        UserMemory.key.ilike(pattern, escape="\\"),
                        UserMemory.value.ilike(pattern, escape="\\"),
                    )
                )
            rows = await db.scalars(
                base.order_by(UserMemory.category, UserMemory.key).limit(_RECALL_LIMIT)
            )
            memories = list(rows.all())

        if not memories:
            if not query:
                return "No memories stored yet."
            return f"No memories matching '{query}'."

        lines = [f"[{m.category}] {m.key}: {m.value}" for m in memories]
        result = "Stored memories:\n" + "\n".join(lines)
        if len(memories) == _RECALL_LIMIT:
            result += f"\n(showing first {_RECALL_LIMIT}; filter with a specific query)"
        return result

    return [remember, recall]
