"""Tests for canvas SSE access control: GET /api/canvas/stream/{conversation_id}."""

import uuid

import pytest

from app.db.models import Conversation


async def _create_conversation(db_session, user_id: uuid.UUID) -> uuid.UUID:
    """Insert a minimal Conversation row for the given user."""
    conv = Conversation(user_id=user_id, title="Canvas Test")
    db_session.add(conv)
    await db_session.flush()
    return conv.id


async def _get_user_id(auth_client) -> uuid.UUID:
    resp = await auth_client.get("/api/auth/me")
    return uuid.UUID(resp.json()["id"])


@pytest.mark.anyio
async def test_canvas_stream_invalid_uuid(auth_client):
    """Malformed conversation_id returns 400."""
    resp = await auth_client.get("/api/canvas/stream/not-a-uuid")
    assert resp.status_code == 400
    assert "invalid" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_canvas_stream_nonexistent_conversation(auth_client):
    """Random UUID that has no conversation row returns 404."""
    resp = await auth_client.get(f"/api/canvas/stream/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_canvas_stream_other_users_conversation(auth_client, db_session, client):
    """A conversation owned by another user returns 404 (no info leak)."""
    from tests.conftest import _register_test_user

    user_id = await _get_user_id(auth_client)
    conv_id = await _create_conversation(db_session, user_id)

    token2 = await _register_test_user(client)
    client.headers["Authorization"] = f"Bearer {token2}"
    resp = await client.get(f"/api/canvas/stream/{conv_id}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_canvas_stream_unauthenticated(client):
    """Unauthenticated request returns 401/403."""
    resp = await client.get(f"/api/canvas/stream/{uuid.uuid4()}")
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_canvas_stream_valid_opens(auth_client, db_session):
    """Valid owned conversation opens the SSE stream (200, text/event-stream)."""
    user_id = await _get_user_id(auth_client)
    conv_id = await _create_conversation(db_session, user_id)

    resp = await auth_client.get(
        f"/api/canvas/stream/{conv_id}",
        headers={"Accept": "text/event-stream"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
