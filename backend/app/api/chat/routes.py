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
            user_id=user.id,
            content=body.content,
            conversation_id=body.conversation_id,
            is_disconnected_func=request.is_disconnected,
            model_override=body.model_override,
            workspace_id=body.workspace_id,
            image_urls=body.image_urls,
            parent_message_id=body.parent_message_id,
            persona_id=body.persona_id,
            workflow_dsl=body.workflow_dsl,
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

    # 获取父消息（人类消息）以重新触发
    parent_msg = await db.scalar(
        select(Message).where(
            Message.id == target_msg.parent_id, Message.conversation_id == conv.id
        )
    )
    # 如果没有父消息（例如重新生成第一条消息），则使用当前 AI 消息的前一条
    if not parent_msg:
        parent_msg = await db.scalar(
            select(Message)
            .where(
                Message.conversation_id == conv.id,
                Message.created_at < target_msg.created_at,
                Message.role == "human",
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )

    if not parent_msg:
        raise HTTPException(
            status_code=400, detail="Could not find parent human message to regenerate"
        )

    # 逻辑删除旧的 AI 消息（或直接替换，这里选择由 Engine 处理或后续由 UI 决定）
    # 目前 run_streaming 会产生一条新的 AI 消息并挂在 parent_msg 下

    engine = AgentEngine(db)

    async def generate() -> AsyncGenerator[str]:
        async for event in engine.run_streaming(
            user_id=user.id,
            content=parent_msg.content,
            conversation_id=body.conversation_id,
            is_disconnected_func=request.is_disconnected,
            model_override=body.model_override,
            workspace_id=body.workspace_id,
            parent_message_id=parent_msg.parent_id,  # 保持树结构
            image_urls=parent_msg.image_urls,
        ):
            yield format_sse(event)

    return StreamingResponse(generate(), media_type="text/event-stream")
