"""User memory management API — list and delete persistent memories."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
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
    model_config = {"from_attributes": True}


@router.get("", response_model=list[MemoryOut])
@limiter.limit("60/minute")
async def list_memories(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserMemory]:
    """List all persistent memories for the current user."""
    rows = await db.scalars(
        select(UserMemory)
        .where(UserMemory.user_id == user.id)
        .order_by(UserMemory.category, UserMemory.key)
    )
    return list(rows.all())


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
