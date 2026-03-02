"""Live Canvas tool — agent pushes HTML visualizations to the frontend."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from langchain_core.tools import BaseTool, tool

logger = structlog.get_logger(__name__)


class CanvasEventBus:
    """In-process publish/subscribe for canvas render events per conversation."""

    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)

    async def publish(self, conversation_id: str, event: dict[str, Any]) -> None:
        for q in list(self._queues[conversation_id]):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop if subscriber is slow

    async def subscribe(self, conversation_id: str) -> AsyncGenerator[dict[str, Any]]:
        """Async generator yielding canvas events for a conversation."""
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=50)
        self._queues[conversation_id].append(q)
        try:
            while True:
                yield await q.get()
        finally:
            try:
                self._queues[conversation_id].remove(q)
            except ValueError:
                pass


# Module-level singleton shared across the process
_canvas_bus = CanvasEventBus()


def get_canvas_bus() -> CanvasEventBus:
    return _canvas_bus


def create_canvas_tool(
    conversation_id: str,
    event_bus: CanvasEventBus | None = None,
) -> BaseTool:
    """Create a canvas_render tool for the given conversation."""
    bus = event_bus or _canvas_bus

    @tool
    async def canvas_render(html: str, title: str = "Canvas") -> str:
        """Render HTML content in the frontend Canvas panel for visualizations.

        Use this to create charts, tables, forms, or any visual content.
        The HTML is rendered in a sandboxed iframe — scripts are allowed.

        Args:
            html: HTML/CSS/JavaScript content to display
            title: Title shown in the canvas panel header
        """
        await bus.publish(
            conversation_id,
            {
                "type": "canvas_render",
                "title": title,
                "html": html,
            },
        )
        logger.info(
            "canvas_rendered",
            conv_id=conversation_id,
            title=title,
            html_bytes=len(html),
        )
        return (
            f"Canvas rendered: '{title}' ({len(html)} chars)."
            " The user can see it in the Canvas panel."
        )

    return canvas_render
