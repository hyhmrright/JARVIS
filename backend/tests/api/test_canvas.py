"""Tests for canvas SSE access control: GET /api/canvas/stream/{conversation_id}."""

import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.canvas import canvas_stream
from app.db.models import Conversation


class _PatchedCanvasSession:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _FakeRequest:
    async def is_disconnected(self) -> bool:
        return True


class _UserStub:
    def __init__(self, user_id: uuid.UUID):
        self.id = user_id


async def _create_conversation(db_session, user_id: uuid.UUID) -> uuid.UUID:
    """Insert a minimal Conversation row for the given user."""
    conv = Conversation(user_id=user_id, title="Canvas Test")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv.id


@pytest.mark.anyio
async def test_canvas_stream_invalid_uuid():
    """Malformed conversation_id returns 400."""
    with pytest.raises(HTTPException) as exc_info:
        await canvas_stream(_FakeRequest(), "not-a-uuid", _UserStub(uuid.uuid4()))

    assert exc_info.value.status_code == 400
    assert "invalid" in str(exc_info.value.detail).lower()


@pytest.mark.anyio
async def test_canvas_stream_nonexistent_conversation(db_session):
    """Random UUID that has no conversation row returns 404."""
    with patch(
        "app.api.canvas.AsyncSessionLocal",
        return_value=_PatchedCanvasSession(db_session),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await canvas_stream(
                _FakeRequest(),
                str(uuid.uuid4()),
                _UserStub(uuid.uuid4()),
            )

    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_canvas_stream_other_users_conversation(db_session):
    """A conversation owned by another user returns 404 (no info leak)."""
    user_id = uuid.uuid4()
    conv_id = await _create_conversation(db_session, user_id)
    other_user = _UserStub(uuid.uuid4())
    with patch(
        "app.api.canvas.AsyncSessionLocal",
        return_value=_PatchedCanvasSession(db_session),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await canvas_stream(_FakeRequest(), str(conv_id), other_user)

    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_canvas_stream_unauthenticated(client):
    """Unauthenticated request returns 401/403."""
    resp = await client.get(f"/api/canvas/stream/{uuid.uuid4()}")
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_canvas_stream_valid_opens(db_session):
    """Valid owned conversation opens the SSE stream (200, text/event-stream)."""
    user_id = uuid.uuid4()
    conv_id = await _create_conversation(db_session, user_id)

    class _FakeCanvasBus:
        async def subscribe(self, conversation_id: str):
            assert conversation_id == str(conv_id)
            yield {"type": "canvas_render", "html": "<div>ok</div>", "title": "Canvas"}

    with patch(
        "app.api.canvas.AsyncSessionLocal",
        return_value=_PatchedCanvasSession(db_session),
    ), patch("app.api.canvas.get_canvas_bus", return_value=_FakeCanvasBus()):
        response = await canvas_stream(
            _FakeRequest(),
            str(conv_id),
            _UserStub(user_id),
        )

    assert response.media_type == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-cache"
