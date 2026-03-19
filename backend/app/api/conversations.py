import json as _json
import secrets
import uuid
from datetime import datetime
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_user_optional
from app.db.models import (
    Conversation,
    ConversationTag,
    Message,
    SharedConversation,
    User,
)
from app.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    title: str = "New Conversation"


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    active_leaf_id: uuid.UUID | None = None
    is_pinned: bool = False
    updated_at: datetime | None = None
    tags: list[str] = []
    model_config = {"from_attributes": True}


class ActiveLeafUpdate(BaseModel):
    active_leaf_id: uuid.UUID


class ConversationUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    persona_override: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("title must not be blank or whitespace-only")
        return v


class ConversationPage(BaseModel):
    items: list[ConversationOut]
    total: int
    offset: int
    limit: int


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
    # New conversations always have zero tags; construct explicitly to avoid
    # lazy-loading the relationship on an async session (MissingGreenlet).
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        active_leaf_id=conv.active_leaf_id,
        is_pinned=conv.is_pinned,
        updated_at=conv.updated_at,
        tags=[],
    )


@router.get("", response_model=ConversationPage)
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ConversationPage:
    total = (
        await db.scalar(
            select(func.count(Conversation.id)).where(Conversation.user_id == user.id)
        )
    ) or 0
    rows = await db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .options(selectinload(Conversation.tags))
        .order_by(Conversation.is_pinned.desc(), Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return ConversationPage(
        items=[
            ConversationOut(
                id=c.id,
                title=c.title,
                active_leaf_id=c.active_leaf_id,
                is_pinned=c.is_pinned,
                updated_at=c.updated_at,
                tags=[t.tag for t in c.tags],
            )
            for c in rows.all()
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    parent_id: uuid.UUID | None = None
    image_urls: list[str] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    created_at: datetime
    model_provider: str | None = None
    model_name: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    is_bookmarked: bool = False
    user_rating: Literal[1, -1] | None = None
    model_config = {"from_attributes": True}


class BookmarkedMessageOut(MessageOut):
    conv_id: uuid.UUID
    conv_title: str


class SearchResult(BaseModel):
    conv_id: uuid.UUID
    title: str
    snippet: str
    updated_at: datetime


@router.get("/search", response_model=list[SearchResult])
async def search_conversations(
    q: str = Query(..., min_length=2, description="Search query, min 2 chars"),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SearchResult]:
    """Full-text search across conversation titles and message content."""
    pattern = f"%{q}%"

    title_rows = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id == user.id,
            Conversation.title.ilike(pattern),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    title_convs = list(title_rows.scalars().all())
    title_ids = {c.id for c in title_convs}

    msg_rows = await db.execute(
        select(Message.conversation_id, Message.content)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.user_id == user.id,
            Message.role.in_(["human", "ai"]),
            Message.content.ilike(pattern),
        )
        .order_by(Message.conversation_id, Message.created_at, Message.id)
        .distinct(Message.conversation_id)
        .limit(limit)
    )
    msg_matches: dict[uuid.UUID, str] = {
        row.conversation_id: row.content for row in msg_rows.all()
    }

    extra_ids = [cid for cid in msg_matches if cid not in title_ids]
    extra_convs: list[Conversation] = []
    if extra_ids:
        extra_rows = await db.execute(
            select(Conversation)
            .where(Conversation.id.in_(extra_ids))
            .order_by(Conversation.updated_at.desc())
        )
        extra_convs = list(extra_rows.scalars().all())

    def _snippet(text: str) -> str:
        idx = text.lower().find(q.lower())
        start = max(0, idx - 50) if idx >= 0 else 0
        return ("..." if start > 0 else "") + text[start : start + 200]

    results: list[SearchResult] = []
    for conv in title_convs + extra_convs:
        snippet_src = msg_matches.get(conv.id, conv.title)
        results.append(
            SearchResult(
                conv_id=conv.id,
                title=conv.title,
                snippet=_snippet(snippet_src),
                updated_at=conv.updated_at,
            )
        )
    return results[:limit]


@router.get("/bookmarked", response_model=list[BookmarkedMessageOut])
async def list_bookmarked_messages(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BookmarkedMessageOut]:
    """Return all bookmarked messages for the current user, newest first."""
    rows = await db.execute(
        select(Message, Conversation.title)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == user.id,
            Message.is_bookmarked == True,  # noqa: E712
        )
        .order_by(Message.created_at.desc())
        .limit(200)
    )
    return [
        BookmarkedMessageOut(
            **MessageOut.model_validate(msg).model_dump(),
            conv_id=msg.conversation_id,
            conv_title=title,
        )
        for msg, title in rows.all()
    ]


@router.get("/tags", response_model=list[str])
async def list_user_tags(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Return all distinct tags used by the current user (for autocomplete)."""
    rows = await db.execute(
        select(ConversationTag.tag)
        .join(Conversation, Conversation.id == ConversationTag.conversation_id)
        .where(Conversation.user_id == user.id)
        .distinct()
        .order_by(ConversationTag.tag)
        .limit(500)
    )
    return list(rows.scalars().all())


@router.get("/{conv_id}/export")
async def export_conversation(
    conv_id: uuid.UUID,
    format: Literal["md", "json", "txt"] = Query("md"),
    token: str | None = Query(None, description="Share token for public access"),
    user: "User | None" = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export conversation as Markdown, JSON, or plain text."""
    conv: Conversation | None = None

    if user:
        conv = await db.scalar(
            select(Conversation).where(
                Conversation.id == conv_id, Conversation.user_id == user.id
            )
        )
    if not conv and token:
        shared = await db.scalar(
            select(SharedConversation).where(SharedConversation.share_token == token)
        )
        if shared and shared.conversation_id == conv_id:
            conv = await db.get(Conversation, shared.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    rows = await db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conv_id,
            Message.role.in_(["human", "ai"]),
        )
        .order_by(Message.created_at)
    )
    messages = list(rows.all())
    safe_title = conv.title.replace("/", "_").replace("\\", "_")

    if format == "md":
        lines = [f"# {conv.title}", ""]
        for msg in messages:
            prefix = "**Human:**" if msg.role == "human" else "**Assistant:**"
            lines.append(f"{prefix}\n{msg.content}")
            lines.append("")
        return Response(
            content="\n".join(lines),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
        )
    elif format == "json":
        data = {
            "id": str(conv.id),
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                }
                for msg in messages
            ],
        }
        disposition = f'attachment; filename="{safe_title}.json"'
        return Response(
            content=_json.dumps(data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": disposition},
        )
    else:  # txt
        lines = []
        for msg in messages:
            prefix = "Human" if msg.role == "human" else "Assistant"
            lines.append(f"{prefix}: {msg.content}")
            lines.append("")
        return Response(
            content="\n".join(lines),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.txt"'},
        )


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
        .limit(500)
    )
    return rows.all()


@router.patch("/{conv_id}/messages/{msg_id}/bookmark", response_model=MessageOut)
async def toggle_bookmark(
    conv_id: uuid.UUID,
    msg_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    """Toggle the bookmark flag on a message."""
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user.id
        )
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msg = await db.scalar(
        select(Message).where(Message.id == msg_id, Message.conversation_id == conv_id)
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.is_bookmarked = not msg.is_bookmarked
    await db.commit()
    await db.refresh(msg)
    logger.info(
        "message_bookmark_toggled",
        user_id=str(user.id),
        msg_id=str(msg_id),
        is_bookmarked=msg.is_bookmarked,
    )
    return msg


class RateMessageRequest(BaseModel):
    # 1 = thumbs up, -1 = thumbs down, None = clear rating
    rating: Literal[1, -1] | None = None


@router.patch("/{conv_id}/messages/{msg_id}/rate", response_model=MessageOut)
async def rate_message(
    conv_id: uuid.UUID,
    msg_id: uuid.UUID,
    body: RateMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    """Set or clear a thumbs-up/thumbs-down rating on a message."""
    msg = await db.scalar(
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Message.id == msg_id,
            Message.conversation_id == conv_id,
            Conversation.user_id == user.id,
            Message.role == "ai",
        )
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.user_rating == body.rating:
        return msg
    msg.user_rating = body.rating
    await db.commit()
    await db.refresh(msg)
    logger.info(
        "message_rated",
        user_id=str(user.id),
        msg_id=str(msg_id),
        rating=body.rating,
    )
    return msg


@router.delete("/{conv_id}/messages/{msg_id}", status_code=204)
async def delete_message(
    conv_id: uuid.UUID,
    msg_id: uuid.UUID,
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
    msg = await db.scalar(
        select(Message).where(Message.id == msg_id, Message.conversation_id == conv_id)
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    await db.delete(msg)
    await db.commit()
    logger.info(
        "message_deleted",
        user_id=str(user.id),
        conv_id=str(conv_id),
        msg_id=str(msg_id),
    )


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


@router.patch("/{conv_id}/active-leaf", status_code=204)
async def set_active_leaf(
    conv_id: uuid.UUID,
    body: ActiveLeafUpdate,
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
    # Verify the message belongs to this conversation
    msg = await db.scalar(
        select(Message).where(
            Message.id == body.active_leaf_id,
            Message.conversation_id == conv_id,
        )
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found in conversation")
    conv.active_leaf_id = body.active_leaf_id
    await db.commit()


@router.patch("/{conv_id}", status_code=204)
async def update_conversation(
    conv_id: uuid.UUID,
    body: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Update mutable conversation fields (title, persona_override)."""
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user.id
        )
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if "title" in body.model_fields_set and body.title:
        conv.title = body.title.strip()
    if "persona_override" in body.model_fields_set:
        conv.persona_override = body.persona_override
    await db.commit()


@router.patch("/{conv_id}/pin", status_code=204)
async def toggle_pin_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Toggle the pinned state of a conversation."""
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user.id
        )
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.is_pinned = not conv.is_pinned
    await db.commit()
    logger.info(
        "conversation_pin_toggled",
        user_id=str(user.id),
        conv_id=str(conv_id),
        is_pinned=conv.is_pinned,
    )


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


# ── Tag endpoints ─────────────────────────────────────────────────────────────

_MAX_TAGS_PER_CONVERSATION = 20


def _normalize_tag(v: str) -> str:
    return v.lower().strip()


class AddTagRequest(BaseModel):
    tag: str = Field(..., max_length=100)

    @field_validator("tag")
    @classmethod
    def normalize(cls, v: str) -> str:
        v = _normalize_tag(v)
        if not v or "," in v or any(c.isspace() for c in v):
            raise ValueError("tag must be non-empty and contain no spaces or commas")
        return v


@router.post("/{conv_id}/tags", response_model=list[str], status_code=201)
async def add_tag(
    conv_id: uuid.UUID,
    body: AddTagRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user.id
        )
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    # Soft limit check — same pattern as keys.py/_MAX_KEYS_PER_USER.
    # A TOCTOU race could allow slightly more than the cap under concurrent
    # requests, but _MAX_TAGS_PER_CONVERSATION is a UX limit, not security.
    tag_count = await db.scalar(
        select(func.count(ConversationTag.id)).where(
            ConversationTag.conversation_id == conv_id
        )
    )
    if (tag_count or 0) >= _MAX_TAGS_PER_CONVERSATION:
        raise HTTPException(
            status_code=422,
            detail=f"A conversation may have at most {_MAX_TAGS_PER_CONVERSATION} tags",
        )
    db.add(ConversationTag(conversation_id=conv_id, tag=body.tag))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()  # tag already exists — idempotent
    rows = await db.scalars(
        select(ConversationTag.tag)
        .where(ConversationTag.conversation_id == conv_id)
        .order_by(ConversationTag.tag)
    )
    return list(rows.all())


@router.delete("/{conv_id}/tags/{tag}", status_code=204)
async def remove_tag(
    conv_id: uuid.UUID,
    tag: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    ct = await db.scalar(
        select(ConversationTag)
        .join(Conversation, Conversation.id == ConversationTag.conversation_id)
        .where(
            ConversationTag.conversation_id == conv_id,
            ConversationTag.tag == _normalize_tag(tag),
            Conversation.user_id == user.id,
        )
    )
    if not ct:
        raise HTTPException(status_code=404, detail="Tag not found")
    await db.delete(ct)
    await db.commit()
