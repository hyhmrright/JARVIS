import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user
from app.db.models import AuditLog, Conversation, Message, User, UserRole
from app.db.session import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """List all users with pagination."""
    offset = (page - 1) * limit
    total = await db.scalar(select(func.count()).select_from(User))
    result = await db.scalars(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    )
    users = result.all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "display_name": u.display_name,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict[str, str]:
    """Update user role or status."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own account")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.role is not None:
        if data.role not in [r.value for r in UserRole]:
            raise HTTPException(status_code=400, detail="Invalid role")
        # Only SUPERADMIN can promote/demote other SUPERADMINs/ADMINs
        if (
            user.role in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value)
            and admin.role != UserRole.SUPERADMIN.value
        ):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        user.role = data.role

    if data.is_active is not None:
        user.is_active = bool(data.is_active)

    await db.commit()
    return {"status": "ok"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict[str, str]:
    """Soft-delete a user."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=400, detail="Cannot deactivate your own account"
        )

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if admin.role != UserRole.SUPERADMIN.value and user.role != UserRole.USER.value:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    user.is_active = False
    await db.commit()
    return {"status": "ok"}


@router.get("/stats")
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Get global system statistics."""
    user_count = await db.scalar(select(func.count()).select_from(User))
    conv_count = await db.scalar(select(func.count()).select_from(Conversation))
    msg_count = await db.scalar(select(func.count()).select_from(Message))

    tokens_result = await db.execute(
        select(
            func.sum(Message.tokens_input).label("total_in"),
            func.sum(Message.tokens_output).label("total_out"),
        )
    )
    tokens = tokens_result.one()

    return {
        "user_count": user_count,
        "conversation_count": conv_count,
        "message_count": msg_count,
        "total_tokens_input": tokens.total_in or 0,
        "total_tokens_output": tokens.total_out or 0,
    }


@router.get("/audit-logs")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    action: str | None = Query(None, description="Filter by action name"),
    user_id: uuid.UUID | None = Query(None, description="Filter by user"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """List audit log entries with optional filtering."""
    offset = (page - 1) * limit
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    count_query = select(func.count()).select_from(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)

    total = await db.scalar(count_query) or 0
    rows = (await db.scalars(query.offset(offset).limit(limit))).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [
            {
                "id": str(row.id),
                "user_id": str(row.user_id) if row.user_id else None,
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
                "extra": row.extra,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }
