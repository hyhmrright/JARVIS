"""Persistent user memory tools — store and recall facts across conversations."""

from __future__ import annotations

import sys
import uuid

import structlog
from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.repositories import MemoryRepository

logger = structlog.get_logger(__name__)

_VALID_CATEGORIES = frozenset({"preference", "fact", "reminder", "general"})
_MAX_VALUE_LEN = 2_000
_RECALL_LIMIT = 100


async def _make_repository(user_id: uuid.UUID) -> tuple[MemoryRepository, AsyncSession]:
    """Return (repo, session) using an isolated DB session.

    The caller MUST call ``await sess.__aexit__(None, None, None)`` after use.
    This is a module-level function so tests can patch it.
    """
    from app.db.session import AsyncSessionLocal

    sess = AsyncSessionLocal()
    db = await sess.__aenter__()
    return MemoryRepository(db), sess


async def _do_remember(
    uid: uuid.UUID, user_id: str, key: str, value: str, category: str
) -> str:
    """Execute the remember operation using MemoryRepository."""
    repo, sess = await _make_repository(uid)
    try:
        mem = await repo.save_memory(uid, key, value, category)
        await sess.__aexit__(None, None, None)
    except Exception:
        await sess.__aexit__(*sys.exc_info())
        raise
    logger.info("user_memory_saved", user_id=user_id, key=key, category=category)
    return f"Memory saved: {mem.key} = {mem.value!r} (category: {category})"


async def _do_recall(uid: uuid.UUID, query: str) -> str:
    """Execute the recall operation using MemoryRepository."""
    repo, sess = await _make_repository(uid)
    try:
        if query:
            memories = await repo.search_memories(uid, query, limit=_RECALL_LIMIT)
        else:
            memories = (await repo.get_memories(uid))[:_RECALL_LIMIT]
        await sess.__aexit__(None, None, None)
    except Exception:
        await sess.__aexit__(*sys.exc_info())
        raise

    if not memories:
        if query:
            return f"No memories matching '{query}'."
        return "No memories stored yet."

    lines = [f"[{m.category}] {m.key}: {m.value}" for m in memories]
    result = "Stored memories:\n" + "\n".join(lines)
    if len(memories) == _RECALL_LIMIT:
        result += f"\n(showing first {_RECALL_LIMIT}; filter with a specific query)"
    return result


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
        return await _do_remember(uid, user_id, key, value, category)

    @tool
    async def recall(query: str = "") -> str:
        """Retrieve facts from persistent memory.

        Returns stored memories, optionally filtered by a substring query against
        the key or value.  Call this when the user asks what you remember about
        them, or when context from past conversations is needed.

        Args:
            query: Optional filter. Leave empty to list all memories.
        """
        return await _do_recall(uid, query)

    return [remember, recall]
