import uuid

import pytest

from app.db.models import Conversation, Message


async def test_create_conversation(auth_client):
    resp = await auth_client.post("/api/conversations", json={"title": "My Chat"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "My Chat"


async def test_list_conversations(auth_client):
    await auth_client.post("/api/conversations", json={"title": "Chat 1"})
    await auth_client.post("/api/conversations", json={"title": "Chat 2"})
    resp = await auth_client.get("/api/conversations")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_delete_conversation(auth_client):
    create = await auth_client.post("/api/conversations", json={"title": "To Delete"})
    conv_id = create.json()["id"]
    resp = await auth_client.delete(f"/api/conversations/{conv_id}")
    assert resp.status_code == 204


async def test_active_leaf_defaults_to_null(auth_client):
    """New conversations must expose active_leaf_id as null."""
    resp = await auth_client.post("/api/conversations", json={"title": "Branch Test"})
    assert resp.status_code == 201
    assert resp.json()["active_leaf_id"] is None


async def test_set_active_leaf_unknown_message_returns_404(auth_client):
    """PATCH /active-leaf with a message not in the conversation returns 404."""
    create = await auth_client.post("/api/conversations", json={"title": "Branch Test"})
    conv_id = create.json()["id"]
    resp = await auth_client.patch(
        f"/api/conversations/{conv_id}/active-leaf",
        json={"active_leaf_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


async def test_set_active_leaf_wrong_conversation_returns_404(auth_client):
    """PATCH /active-leaf with a message not in this conversation returns 404."""
    # Use a random UUID that belongs to no conversation
    fake_conv_id = str(uuid.uuid4())
    resp = await auth_client.patch(
        f"/api/conversations/{fake_conv_id}/active-leaf",
        json={"active_leaf_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_search_rejects_single_char(auth_client):
    resp = await auth_client.get("/api/conversations/search?q=a")
    assert resp.status_code == 422  # Pydantic min_length=2 returns 422


@pytest.mark.anyio
async def test_search_returns_empty_list_for_no_match(auth_client):
    resp = await auth_client.get("/api/conversations/search?q=zzznomatch")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_search_finds_conversation_by_title(auth_client, db_session):
    from app.core.security import decode_access_token

    token = auth_client.headers["Authorization"].split(" ")[1]
    user_id = decode_access_token(token)
    conv = Conversation(user_id=user_id, title="Python tutorials for beginners")
    db_session.add(conv)
    await db_session.commit()
    resp = await auth_client.get("/api/conversations/search?q=Python")
    assert resp.status_code == 200
    results = resp.json()
    assert any(r["conv_id"] == str(conv.id) for r in results)
    result = next(r for r in results if r["conv_id"] == str(conv.id))
    assert "title" in result
    assert "snippet" in result
    assert "updated_at" in result


@pytest.mark.anyio
async def test_search_finds_by_message_content(auth_client, db_session):
    from app.core.security import decode_access_token

    token = auth_client.headers["Authorization"].split(" ")[1]
    user_id = decode_access_token(token)
    conv = Conversation(user_id=user_id, title="Generic conversation")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(
        conversation_id=conv.id,
        role="human",
        content="Explain quantum entanglement in simple terms",
    )
    db_session.add(msg)
    await db_session.commit()
    resp = await auth_client.get("/api/conversations/search?q=quantum")
    assert resp.status_code == 200
    assert any(r["conv_id"] == str(conv.id) for r in resp.json())
