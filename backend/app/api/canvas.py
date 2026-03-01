"""Canvas SSE endpoint — streams canvas render events to the frontend."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.db.models import User
from app.tools.canvas_tool import get_canvas_bus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/canvas", tags=["canvas"])


@router.get("/stream/{conversation_id}")
async def canvas_stream(
    conversation_id: str,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE stream of canvas render events for a conversation.

    The frontend connects here and receives canvas_render events
    whenever the agent calls the canvas_render tool.
    """

    async def _generate() -> AsyncGenerator[str]:
        bus = get_canvas_bus()
        logger.info(
            "canvas_stream_connected",
            user_id=str(user.id),
            conv_id=conversation_id,
        )
        async for event in bus.subscribe(conversation_id):
            yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
