"""Usage statistics API — token consumption per user."""

from __future__ import annotations

from datetime import date, timedelta

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import Conversation, Message, User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/summary")
async def get_usage_summary(
    days: int = 30,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return daily token usage for the past N days, grouped by provider."""
    if days < 1 or days > 365:
        days = 30

    since = date.today() - timedelta(days=days)

    rows = await db.execute(
        select(
            func.date(Message.created_at).label("day"),
            Message.model_provider,
            func.coalesce(func.sum(Message.tokens_input), 0).label("tokens_in"),
            func.coalesce(func.sum(Message.tokens_output), 0).label("tokens_out"),
            func.count().label("message_count"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == user.id,
            Message.role == "ai",
            Message.created_at >= since,
        )
        .group_by(func.date(Message.created_at), Message.model_provider)
        .order_by(func.date(Message.created_at))
    )
    daily = [
        {
            "day": str(r.day),
            "provider": r.model_provider or "unknown",
            "tokens_in": int(r.tokens_in),
            "tokens_out": int(r.tokens_out),
            "messages": int(r.message_count),
        }
        for r in rows.all()
    ]
    return {
        "daily": daily,
        "total_tokens_in": sum(d["tokens_in"] for d in daily),
        "total_tokens_out": sum(d["tokens_out"] for d in daily),
        "total_messages": sum(d["messages"] for d in daily),
        "days": days,
    }
