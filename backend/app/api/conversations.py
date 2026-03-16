import secrets
import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import Conversation, Message, SharedConversation, User
from app.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    title: str = "New Conversation"


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    model_config = {"from_attributes": True}


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    conv = Conversation(user_id=user.id, title=body.title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    logger.info(
        "conversation_created",
        user_id=str(user.id),
        conv_id=str(conv.id),
        title=conv.title,
    )
    return conv


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationOut]:
    rows = await db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return rows.all()


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    image_urls: list[str] | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


@router.get("/{conv_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user.id
        )
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
    )
    return rows.all()


@router.delete("/{conv_id}", status_code=204)
async def delete_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user.id
        )
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)
    await db.commit()
    logger.info("conversation_deleted", user_id=str(user.id), conv_id=str(conv_id))


@router.post("/{conv_id}/share", response_model=dict)
async def share_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user.id
        )
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if already shared
    existing = await db.scalar(
        select(SharedConversation).where(SharedConversation.conversation_id == conv_id)
    )
    if existing:
        return {"token": existing.share_token}

    new_share = SharedConversation(
        conversation_id=conv_id,
        share_token=secrets.token_urlsafe(32),
    )
    db.add(new_share)
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent request already created a share for this conversation.
        await db.rollback()
        existing = await db.scalar(
            select(SharedConversation).where(
                SharedConversation.conversation_id == conv_id
            )
        )
        if existing is None:
            raise HTTPException(
                status_code=500, detail="Share creation conflict; please retry."
            ) from None
        return {"token": existing.share_token}
    return {"token": new_share.share_token}
