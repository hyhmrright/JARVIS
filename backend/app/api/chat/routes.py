from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat.schemas import ChatRequest, RegenerateRequest
from app.api.chat.sse import format_sse
from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.db.models import Conversation, Message, User
from app.db.session import get_db
from app.services.agent_engine import AgentEngine

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
    logger.info(
        "chat_stream_started",
        user_id=str(user.id),
        conv_id=str(body.conversation_id),
    )

    engine = AgentEngine(db)

    async def generate() -> AsyncGenerator[str]:
        async for event in engine.run_streaming(
            user.id,
            body.content,
            body.conversation_id,
            request.is_disconnected,
            model_override=body.model_override,
        ):
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

    # 构建合成请求
    engine = AgentEngine(db)

    async def generate() -> AsyncGenerator[str]:
        # 注意：此处 regenerate 逻辑应在 Engine 中进一步完善，暂用 run_streaming 模拟
        async for event in engine.run_streaming(
            user.id,
            ".",  # 重新生成标志
            body.conversation_id,
            request.is_disconnected,
            model_override=body.model_override,
        ):
            yield format_sse(event)

    return StreamingResponse(generate(), media_type="text/event-stream")
