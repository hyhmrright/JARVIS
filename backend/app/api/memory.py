"""User memory management API — list, update, and delete persistent memories."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PaginationParams, get_current_user
from app.core.limiter import limiter
from app.db.models import User, UserMemory
from app.db.session import get_db

router = APIRouter(prefix="/api/memories", tags=["memories"])


class MemoryOut(BaseModel):
    id: uuid.UUID
    key: str
    value: str
    category: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MemoryUpdate(BaseModel):
    value: str = Field(min_length=1, max_length=4000)


class MemoryPage(BaseModel):
    items: list[MemoryOut]
    total: int


@router.get("", response_model=MemoryPage)
@limiter.limit("60/minute")
async def list_memories(
    request: Request,
    pagination: Annotated[PaginationParams, Depends()],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryPage:
    """List persistent memories for the current user."""
    total = (
        await db.scalar(
            select(func.count(UserMemory.id)).where(UserMemory.user_id == user.id)
        )
    ) or 0
    rows = await db.scalars(
        select(UserMemory)
        .where(UserMemory.user_id == user.id)
        .order_by(UserMemory.category, UserMemory.key)
        .limit(pagination.limit)
        .offset(pagination.skip)
    )
    return MemoryPage(items=list(rows.all()), total=total)


@router.put("/{memory_id}", response_model=MemoryOut)
@limiter.limit("30/minute")
async def update_memory(
    request: Request,
    memory_id: uuid.UUID,
    body: MemoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserMemory:
    """Update the value of an existing memory."""
    memory = await db.scalar(
        select(UserMemory).where(
            UserMemory.id == memory_id, UserMemory.user_id == user.id
        )
    )
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    memory.value = body.value
    await db.commit()
    return memory


@router.delete("/{memory_id}", status_code=204)
@limiter.limit("60/minute")
async def delete_memory(
    request: Request,
    memory_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a specific memory by ID."""
    memory = await db.scalar(
        select(UserMemory).where(
            UserMemory.id == memory_id, UserMemory.user_id == user.id
        )
    )
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    await db.delete(memory)
    await db.commit()


@router.delete("", status_code=204)
@limiter.limit("3/minute")
async def clear_all_memories(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete all memories for the current user."""
    await db.execute(delete(UserMemory).where(UserMemory.user_id == user.id))
    await db.commit()
