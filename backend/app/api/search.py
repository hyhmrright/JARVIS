"""Unified keyword search across messages, documents, and user memories."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.db.models import (
    Conversation,
    Document,
    Message,
    User,
    UserMemory,
    WorkspaceMember,
)
from app.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])

_SNIPPET_RADIUS = 80  # characters each side of the match


def _make_snippet(text_val: str, keyword: str) -> str:
    """Extract a snippet around the first case-insensitive match of keyword."""
    lower_text = text_val.lower()
    lower_kw = keyword.lower()
    pos = lower_text.find(lower_kw)
    if pos == -1:
        return text_val[: _SNIPPET_RADIUS * 2]
    start = max(0, pos - _SNIPPET_RADIUS)
    end = pos + len(keyword) + _SNIPPET_RADIUS
    return text_val[start:end]


class SearchResultItem(BaseModel):
    type: Literal["message", "document", "memory"]
    id: uuid.UUID
    snippet: str
    created_at: str
    # message-specific
    conversation_id: uuid.UUID | None = None
    conversation_title: str | None = None
    # document-specific
    filename: str | None = None
    file_type: str | None = None


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total: int


@router.get("", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search(
    request: Request,
    q: str = Query(..., min_length=3, max_length=200),
    types: str = Query(default="messages,documents,memories"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search messages, documents, and memories by keyword."""
    valid_types = {"messages", "documents", "memories"}
    requested = {t.strip() for t in types.split(",") if t.strip()}
    invalid = requested - valid_types
    if invalid:
        valid_str = ", ".join(sorted(valid_types))
        invalid_str = ", ".join(sorted(invalid))
        raise HTTPException(
            status_code=422,
            detail=f"Invalid types: {invalid_str}. Valid: {valid_str}",
        )

    pattern = f"%{q}%"
    uid = user.id
    workspace_subq = select(WorkspaceMember.workspace_id).where(
        WorkspaceMember.user_id == uid
    )

    args = (db, uid, pattern, q)
    tasks = []
    if "messages" in requested:
        tasks.append(_search_messages(*args, workspace_subq, date_from, date_to, limit))
    if "documents" in requested:
        tasks.append(
            _search_documents(*args, workspace_subq, date_from, date_to, limit)
        )
    if "memories" in requested:
        tasks.append(_search_memories(*args, date_from, date_to, limit))

    gathered = await asyncio.gather(*tasks)
    all_results: list[SearchResultItem] = []
    for batch in gathered:
        all_results.extend(batch)
    all_results.sort(key=lambda r: r.created_at, reverse=True)

    return SearchResponse(results=all_results, total=len(all_results))


async def _search_messages(
    db: AsyncSession,
    uid: uuid.UUID,
    pattern: str,
    keyword: str,
    workspace_subq: Any,
    date_from: date | None,
    date_to: date | None,
    limit: int,
) -> list[SearchResultItem]:
    """Search messages in the user's own conversations or workspace conversations."""
    stmt = (
        select(Message, Conversation.title)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.content.ilike(pattern),
            Message.role.in_(["human", "ai"]),
            (Conversation.user_id == uid)
            | (Conversation.workspace_id.in_(workspace_subq)),
        )
    )
    if date_from:
        stmt = stmt.where(Message.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Message.created_at <= date_to)
    stmt = stmt.order_by(Message.created_at.desc()).limit(limit)

    rows = await db.execute(stmt)
    results = []
    for msg, conv_title in rows:
        results.append(
            SearchResultItem(
                type="message",
                id=msg.id,
                snippet=_make_snippet(msg.content, keyword),
                created_at=msg.created_at.isoformat(),
                conversation_id=msg.conversation_id,
                conversation_title=conv_title,
            )
        )
    return results


async def _search_documents(
    db: AsyncSession,
    uid: uuid.UUID,
    pattern: str,
    keyword: str,
    workspace_subq: Any,
    date_from: date | None,
    date_to: date | None,
    limit: int,
) -> list[SearchResultItem]:
    """Search non-deleted documents owned by the user or accessible via workspace."""
    stmt = select(Document).where(
        Document.filename.ilike(pattern),
        Document.is_deleted.is_(False),
        (Document.user_id == uid)
        | (
            (Document.workspace_id.isnot(None))
            & (Document.workspace_id.in_(workspace_subq))
        ),
    )
    if date_from:
        stmt = stmt.where(Document.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Document.created_at <= date_to)
    stmt = stmt.order_by(Document.created_at.desc()).limit(limit)

    rows = await db.scalars(stmt)
    results = []
    for doc in rows.all():
        results.append(
            SearchResultItem(
                type="document",
                id=doc.id,
                snippet=_make_snippet(doc.filename, keyword),
                created_at=doc.created_at.isoformat(),
                filename=doc.filename,
                file_type=doc.file_type,
            )
        )
    return results


async def _search_memories(
    db: AsyncSession,
    uid: uuid.UUID,
    pattern: str,
    keyword: str,
    date_from: date | None,
    date_to: date | None,
    limit: int,
) -> list[SearchResultItem]:
    """Search user memories by value text."""
    stmt = select(UserMemory).where(
        UserMemory.user_id == uid,
        UserMemory.value.ilike(pattern),
    )
    if date_from:
        stmt = stmt.where(UserMemory.created_at >= date_from)
    if date_to:
        stmt = stmt.where(UserMemory.created_at <= date_to)
    stmt = stmt.order_by(UserMemory.created_at.desc()).limit(limit)

    rows = await db.scalars(stmt)
    results = []
    for mem in rows.all():
        results.append(
            SearchResultItem(
                type="memory",
                id=mem.id,
                snippet=_make_snippet(mem.value, keyword),
                created_at=mem.created_at.isoformat(),
            )
        )
    return results
