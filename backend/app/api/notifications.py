"""Notification API endpoints."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PaginationParams, get_current_user
from app.core.limiter import limiter
from app.db.models import Notification, User
from app.db.session import get_db

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    is_read: bool
    action_url: str | None = None
    metadata_json: dict
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[NotificationOut])
@limiter.limit("60/minute")
async def list_notifications(
    request: Request,
    pagination: Annotated[PaginationParams, Depends()],
    include_read: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Notification]:
    """List recent notifications for the user."""
    stmt = select(Notification).where(Notification.user_id == user.id)
    if not include_read:
        stmt = stmt.where(Notification.is_read.is_(False))

    stmt = stmt.order_by(Notification.created_at.desc()).limit(pagination.limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/unread-count")
@limiter.limit("60/minute")
async def get_unread_count(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the count of unread notifications."""
    count = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
    )
    return {"count": count or 0}


@router.patch("/{notification_id}/read", status_code=204)
@limiter.limit("60/minute")
async def mark_as_read(
    request: Request,
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Mark a notification as read."""
    notification = await db.get(Notification, notification_id)
    if not notification or notification.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    await db.commit()


@router.post("/mark-all-read", status_code=204)
@limiter.limit("60/minute")
async def mark_all_read(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Mark all unread notifications as read."""
    from sqlalchemy import update

    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()


@router.delete("/{notification_id}", status_code=204)
@limiter.limit("30/minute")
async def delete_notification(
    request: Request,
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a single notification."""
    notification = await db.get(Notification, notification_id)
    if not notification or notification.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.delete(notification)
    await db.commit()


@router.delete("", status_code=204)
@limiter.limit("30/minute")
async def delete_all_notifications(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete all notifications for the current user."""
    await db.execute(delete(Notification).where(Notification.user_id == user.id))
    await db.commit()
