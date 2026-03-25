"""Usage statistics API — token consumption per user."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_workspace_member
from app.core.pricing import estimate_cost
from app.db.models import Conversation, Message, User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/summary")
async def get_usage_summary(
    days: int = 30,
    workspace_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return daily token usage for the past N days, grouped by provider."""
    if days < 1 or days > 365:
        days = 30

    since = date.today() - timedelta(days=days)

    stmt = select(
        func.date(Message.created_at).label("day"),
        Message.model_provider,
        Message.model_name,
        func.coalesce(func.sum(Message.tokens_input), 0).label("tokens_in"),
        func.coalesce(func.sum(Message.tokens_output), 0).label("tokens_out"),
        func.count().label("message_count"),
    ).join(Conversation, Message.conversation_id == Conversation.id)

    if workspace_id:
        await require_workspace_member(workspace_id, user, db)
        stmt = stmt.where(Conversation.workspace_id == workspace_id)
    else:
        stmt = stmt.where(Conversation.user_id == user.id)

    stmt = stmt.where(
        Message.role == "ai",
        Message.created_at >= since,
    ).group_by(
        func.date(Message.created_at), Message.model_provider, Message.model_name
    )
    stmt = stmt.order_by(func.date(Message.created_at))

    rows = await db.execute(stmt)
    daily = [
        {
            "day": str(r.day),
            "provider": r.model_provider or "unknown",
            "model": r.model_name or "unknown",
            "tokens_in": int(r.tokens_in),
            "tokens_out": int(r.tokens_out),
            "messages": int(r.message_count),
            "estimated_cost_usd": estimate_cost(
                r.model_provider or "",
                r.model_name or "",
                int(r.tokens_in),
                int(r.tokens_out),
            ),
        }
        for r in rows.all()
    ]
    return {
        "daily": daily,
        "total_tokens_in": sum(d["tokens_in"] for d in daily),
        "total_tokens_out": sum(d["tokens_out"] for d in daily),
        "total_messages": sum(d["messages"] for d in daily),
        "total_estimated_cost_usd": sum(d["estimated_cost_usd"] for d in daily),
        "days": days,
    }
