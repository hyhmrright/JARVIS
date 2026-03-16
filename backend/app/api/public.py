import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, SharedConversation
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
    token: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Any:
    share = await db.scalar(
        select(SharedConversation).where(SharedConversation.id == token)
    )
    if not share:
        raise HTTPException(status_code=404, detail="Shared conversation not found")

    conv = await db.scalar(
        select(Conversation).where(Conversation.id == share.conversation_id)
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    messages = rows.all()

    # For now we just return the flat list of messages.
    # In a real tree UI we might want to return the whole tree,
    # but for sharing, the 'activeMessages' logic is usually what's wanted.
    # However, since this is a simple share, let's just return all messages in order.

    return {
        "title": conv.title,
        "messages": messages,
    }
