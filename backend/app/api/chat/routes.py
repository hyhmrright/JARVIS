"""FastAPI route handlers for the chat streaming API."""

from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat.context import build_chat_context
from app.api.chat.schemas import ChatRequest, RegenerateRequest
from app.api.chat.sse import (
    format_sse,
)
from app.api.deps import get_current_user, get_llm_config
from app.core.limiter import limiter
from app.db.models import Conversation, Message, User
from app.db.session import get_db
from app.services.chat_stream_service import ChatStreamService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
@limiter.limit("30/minute")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    llm = await get_llm_config(user=user, db=db, workspace_id=body.workspace_id)
    ctx = await build_chat_context(body, user, db, llm)
    llm = ctx.llm or llm

    logger.info(
        "chat_stream_started",
        user_id=str(user.id),
        conv_id=str(body.conversation_id),
    )

    service = ChatStreamService(db)

    async def generate() -> AsyncGenerator[str]:
        async for event in service.execute_stream(
            ctx, llm, str(user.id), request.is_disconnected
        ):
            if isinstance(event, str):
                yield event
            else:
                yield format_sse(event)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/regenerate")
@limiter.limit("30/minute")
async def chat_regenerate(
    request: Request,
    body: RegenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    llm = await get_llm_config(user=user, db=db, workspace_id=body.workspace_id)
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404)

    target_msg = await db.scalar(
        select(Message).where(
            Message.id == body.message_id, Message.conversation_id == conv.id
        )
    )
    if not target_msg:
        raise HTTPException(status_code=404, detail="Message not found")

    synthetic_req = ChatRequest(
        conversation_id=body.conversation_id,
        content=".",
        workspace_id=body.workspace_id,
        model_override=body.model_override,
    )
    ctx = await build_chat_context(
        synthetic_req, user, db, llm, _regen_parent_id=target_msg.parent_id
    )
    llm = ctx.llm or llm

    service = ChatStreamService(db)

    async def generate() -> AsyncGenerator[str]:
        async for event in service.execute_stream(
            ctx, llm, str(user.id), request.is_disconnected
        ):
            if isinstance(event, str):
                yield event
            else:
                yield format_sse(event)

    return StreamingResponse(generate(), media_type="text/event-stream")

    return StreamingResponse(generate(), media_type="text/event-stream")
