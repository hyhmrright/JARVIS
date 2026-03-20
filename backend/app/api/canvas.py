"""Canvas SSE endpoint — streams canvas render events to the frontend."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import get_current_user_query_token
from app.db.models import Conversation, User
from app.db.session import AsyncSessionLocal
from app.tools.canvas_tool import get_canvas_bus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/canvas", tags=["canvas"])


@router.get("/stream/{conversation_id}")
async def canvas_stream(
    request: Request,
    conversation_id: str,
    user: User = Depends(get_current_user_query_token),
) -> StreamingResponse:
    """SSE stream of canvas render events for a conversation.

    The frontend connects here and receives canvas_render events
    whenever the agent calls the canvas_render tool.
    """
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid conversation_id") from exc

    # Perform the ownership check in a short-lived session that is closed
    # before streaming begins.  Holding get_db() open for the lifetime of an
    # SSE stream would exhaust the connection pool.
    async with AsyncSessionLocal() as db:
        conv = await db.scalar(
            select(Conversation).where(
                Conversation.id == conv_uuid,
                Conversation.user_id == user.id,
            )
        )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Use the normalised UUID string as the bus key so it matches whatever
    # form the publisher used (uuid.UUID.__str__ always returns lowercase
    # hyphenated form).
    norm_conv_id = str(conv_uuid)

    async def _generate() -> AsyncGenerator[str]:
        bus = get_canvas_bus()
        logger.info(
            "canvas_stream_connected",
            user_id=str(user.id),
            conv_id=norm_conv_id,
        )
        try:
            async for event in bus.subscribe(norm_conv_id):
                if await request.is_disconnected():
                    logger.info(
                        "canvas_stream_disconnected",
                        user_id=str(user.id),
                        conv_id=norm_conv_id,
                    )
                    break
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
        except Exception:
            logger.exception(
                "canvas_stream_error",
                user_id=str(user.id),
                conv_id=norm_conv_id,
            )
            yield 'event: error\ndata: {"type":"stream_error"}\n\n'

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
