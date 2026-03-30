# backend/app/services/repositories.py
"""Repository classes for tool-layer DB access.

Tools must not import AsyncSessionLocal directly.  Instead they receive
a repository instance that wraps a session, making them testable without
a live database connection.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CronJob, UserMemory


class MemoryRepository:
    """Read and write UserMemory rows for a given user."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_memories(
        self, user_id: uuid.UUID, limit: int | None = None
    ) -> list[UserMemory]:
        q = select(UserMemory).where(UserMemory.user_id == user_id)
        if limit is not None:
            q = q.limit(limit)
        result = await self._db.scalars(q)
        return list(result.all())

    async def get_memory_by_key(
        self, user_id: uuid.UUID, key: str
    ) -> UserMemory | None:
        return await self._db.scalar(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.key == key,
            )
        )

    async def save_memory(
        self,
        user_id: uuid.UUID,
        key: str,
        value: str,
        category: str = "general",
    ) -> UserMemory:
        """Upsert: update existing key or insert new row."""
        existing = await self.get_memory_by_key(user_id, key)
        if existing is not None:
            existing.value = value
            existing.category = category
            existing.updated_at = datetime.now(UTC)
            await self._db.flush()
            return existing
        mem = UserMemory(
            user_id=user_id,
            key=key,
            value=value,
            category=category,
        )
        self._db.add(mem)
        await self._db.flush()
        return mem

    async def delete_memory(self, memory_id: uuid.UUID) -> bool:
        """Return True if deleted, False if not found."""
        mem = await self._db.get(UserMemory, memory_id)
        if mem is None:
            return False
        await self._db.delete(mem)
        await self._db.flush()
        return True

    async def search_memories(
        self, user_id: uuid.UUID, query: str, limit: int = 100
    ) -> list[UserMemory]:
        result = await self._db.scalars(
            select(UserMemory)
            .where(
                UserMemory.user_id == user_id,
                or_(
                    UserMemory.key.ilike(f"%{query}%"),
                    UserMemory.value.ilike(f"%{query}%"),
                ),
            )
            .limit(limit)
        )
        return list(result.all())


class CronRepository:
    """Read CronJob rows for a given user (tools need read-only access)."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_job(self, job_id: uuid.UUID) -> CronJob | None:
        return await self._db.scalar(select(CronJob).where(CronJob.id == job_id))

    async def list_jobs(self, user_id: uuid.UUID) -> list[CronJob]:
        result = await self._db.scalars(
            select(CronJob).where(
                CronJob.user_id == user_id,
                CronJob.is_active == True,  # noqa: E712
            )
        )
        return list(result.all())
