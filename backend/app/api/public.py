from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.limiter import limiter
from app.db.models import Message, SharedConversation
from app.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/public", tags=["public"])


class PublicMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str
    image_urls: list[str] | None = None


class PublicConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    messages: list[PublicMessageOut]


@router.get("/share/{token}", response_model=PublicConversationOut)
@limiter.limit("60/minute")
async def get_shared_conversation(
    request: Request,
    token: Annotated[str, Path(min_length=40, max_length=64)],
    db: AsyncSession = Depends(get_db),
) -> Any:
    share = await db.scalar(
        select(SharedConversation)
        .where(SharedConversation.share_token == token)
        .options(selectinload(SharedConversation.conversation))
    )
    if not share:
        raise HTTPException(status_code=404, detail="Shared conversation not found")

    conv = share.conversation
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    messages = rows.all()

    return {
        "title": conv.title,
        "messages": messages,
    }
