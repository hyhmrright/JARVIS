"""Unit tests for chat API endpoints."""

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.agent.protocol import TextDeltaEvent


@pytest.mark.asyncio
async def test_chat_stream_success(auth_client: AsyncClient):
    """Test that the chat stream route delegates to AgentEngine and formats SSE."""
    payload = {"content": "Hello", "conversation_id": str(uuid.uuid4())}

    async def mock_run_streaming(*args, **kwargs):
        yield TextDeltaEvent(delta="Hi ")
        yield TextDeltaEvent(delta="there")

    with patch("app.api.chat.routes.AgentEngine") as mock_engine:
        mock_instance = mock_engine.return_value
        mock_instance.run_streaming = mock_run_streaming

        response = await auth_client.post("/api/chat/stream", json=payload)

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        lines = response.text.strip().split("\n\n")
        assert len(lines) == 2
        assert "Hi " in lines[0]
        assert "there" in lines[1]


@pytest.mark.asyncio
async def test_chat_regenerate_success(auth_client: AsyncClient):
    """Test the chat regenerate route delegates to AgentEngine."""
    payload = {"conversation_id": str(uuid.uuid4())}

    async def mock_run_streaming(*args, **kwargs):
        yield TextDeltaEvent(delta="Regenerated")

    with patch("app.api.chat.routes.AgentEngine") as mock_engine:
        mock_instance = mock_engine.return_value
        mock_instance.run_streaming = mock_run_streaming

        response = await auth_client.post("/api/chat/regenerate", json=payload)

        assert response.status_code == 200
        assert "Regenerated" in response.text
