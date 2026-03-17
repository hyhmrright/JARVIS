from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Message, SharedConversation
from app.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/public", tags=["public"])


class PublicMessageOut(BaseModel):
    role: str
    content: str
    image_urls: list[str] | None = None
    model_config = {"from_attributes": True}


class PublicConversationOut(BaseModel):
    title: str
    messages: list[PublicMessageOut]


@router.get("/share/{token}", response_model=PublicConversationOut)
async def get_shared_conversation(
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
