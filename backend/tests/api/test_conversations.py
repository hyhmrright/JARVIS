import uuid

import pytest

from app.core.security import decode_access_token
from app.db.models import Conversation, Message


def _user_id(auth_client) -> uuid.UUID:
    """Extract the authenticated user's UUID from an auth_client fixture."""
    token = auth_client.headers["Authorization"].split(" ")[1]
    return uuid.UUID(decode_access_token(token))


def _uid_from_headers(headers: dict) -> uuid.UUID:
    """Extract a user UUID from a raw Authorization header dict."""
    token = headers["Authorization"].split(" ")[1]
    return uuid.UUID(decode_access_token(token))


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

    user_id = _user_id(auth_client)
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

    user_id = _user_id(auth_client)
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


@pytest.mark.anyio
async def test_export_markdown_format(auth_client, db_session):

    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="My Export Test")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(Message(conversation_id=conv.id, role="human", content="Hello AI"))
    db_session.add(Message(conversation_id=conv.id, role="ai", content="Hello human"))
    await db_session.commit()
    resp = await auth_client.get(f"/api/conversations/{conv.id}/export?format=md")
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    assert "My Export Test" in resp.text
    assert "**Human:**" in resp.text
    assert "**Assistant:**" in resp.text
    assert "Hello AI" in resp.text


@pytest.mark.anyio
async def test_export_json_format(auth_client, db_session):
    import json as _json

    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="JSON Export")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(Message(conversation_id=conv.id, role="human", content="Question"))
    await db_session.commit()
    resp = await auth_client.get(f"/api/conversations/{conv.id}/export?format=json")
    assert resp.status_code == 200
    data = _json.loads(resp.content)
    assert data["title"] == "JSON Export"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == "human"


@pytest.mark.anyio
async def test_export_txt_format(auth_client, db_session):

    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="TXT Export")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(Message(conversation_id=conv.id, role="human", content="Test msg"))
    await db_session.commit()
    resp = await auth_client.get(f"/api/conversations/{conv.id}/export?format=txt")
    assert resp.status_code == 200
    assert "Human: Test msg" in resp.text


@pytest.mark.anyio
async def test_export_returns_404_for_wrong_user(
    auth_client, second_user_auth_headers, db_session
):

    # Create a conversation owned by second user
    user2_id = _uid_from_headers(second_user_auth_headers)
    conv = Conversation(user_id=user2_id, title="Private")
    db_session.add(conv)
    await db_session.commit()
    # Try to export as first user (auth_client)
    resp = await auth_client.get(f"/api/conversations/{conv.id}/export")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_patch_conversation_sets_persona(auth_client, db_session):

    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Patch test")
    db_session.add(conv)
    await db_session.commit()
    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}",
        json={"persona_override": "You are a Socratic tutor."},
    )
    assert resp.status_code == 204
    await db_session.refresh(conv)
    assert conv.persona_override == "You are a Socratic tutor."


@pytest.mark.anyio
async def test_patch_conversation_clears_persona(auth_client, db_session):

    user_id = _user_id(auth_client)
    conv = Conversation(
        user_id=user_id, title="Clear test", persona_override="Old value"
    )
    db_session.add(conv)
    await db_session.commit()
    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}",
        json={"persona_override": None},
    )
    assert resp.status_code == 204
    await db_session.refresh(conv)
    assert conv.persona_override is None


@pytest.mark.anyio
async def test_patch_conversation_renames_title(auth_client, db_session):

    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Old Title")
    db_session.add(conv)
    await db_session.commit()
    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}",
        json={"title": "New Title"},
    )
    assert resp.status_code == 204
    await db_session.refresh(conv)
    assert conv.title == "New Title"


@pytest.mark.anyio
async def test_patch_conversation_empty_title_returns_422(auth_client, db_session):

    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Keep This")
    db_session.add(conv)
    await db_session.commit()
    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}",
        json={"title": ""},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_patch_conversation_whitespace_title_returns_422(auth_client, db_session):

    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Keep This")
    db_session.add(conv)
    await db_session.commit()
    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}",
        json={"title": "   "},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_patch_conversation_omitting_title_preserves_it(auth_client, db_session):

    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Unchanged")
    db_session.add(conv)
    await db_session.commit()
    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}",
        json={"persona_override": "tutor"},
    )
    assert resp.status_code == 204
    await db_session.refresh(conv)
    assert conv.title == "Unchanged"


@pytest.mark.anyio
async def test_messages_include_tool_calls_field(auth_client, db_session):
    from typing import Any

    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Tool calls test")
    db_session.add(conv)
    await db_session.flush()
    tool_calls_data: list[dict[str, Any]] = [
        {"name": "rag_search", "id": "call_abc123", "args": {"query": "test"}}
    ]
    ai_msg = Message(
        conversation_id=conv.id,
        role="ai",
        content="Here are the results.",
        tool_calls=tool_calls_data,
    )
    db_session.add(ai_msg)
    await db_session.commit()
    resp = await auth_client.get(f"/api/conversations/{conv.id}/messages")
    assert resp.status_code == 200
    msgs = resp.json()
    ai = next(m for m in msgs if m["role"] == "ai")
    assert "tool_calls" in ai
    assert ai["tool_calls"][0]["name"] == "rag_search"


@pytest.mark.anyio
async def test_export_accessible_via_share_token(client, db_session):
    """Export should work for anonymous users who have a valid share token."""
    import uuid as _uuid

    # Register a user and create a conversation
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": f"sharetest_{_uuid.uuid4().hex[:6]}@example.com",
            "password": "password123",
        },
    )
    assert resp.status_code == 201
    owner_token = resp.json()["access_token"]
    owner_id = decode_access_token(owner_token)
    conv = Conversation(user_id=owner_id, title="Shared Conversation")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(
        Message(conversation_id=conv.id, role="human", content="Shared message")
    )
    from app.db.models import SharedConversation

    share = SharedConversation(
        conversation_id=conv.id, share_token="test-share-token-xyz"
    )
    db_session.add(share)
    await db_session.commit()
    # Access export without auth but with share token
    resp = await client.get(
        f"/api/conversations/{conv.id}/export?token=test-share-token-xyz"
    )
    assert resp.status_code == 200
    assert "Shared Conversation" in resp.text


# ---------------------------------------------------------------------------
# Conversation pinning
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_pin_conversation(auth_client, db_session):
    """Pinning a conversation sets is_pinned=True."""
    uid = _user_id(auth_client)
    conv = Conversation(user_id=uid, title="Pinnable")
    db_session.add(conv)
    await db_session.commit()

    resp = await auth_client.patch(f"/api/conversations/{conv.id}/pin")
    assert resp.status_code == 204
    await db_session.refresh(conv)
    assert conv.is_pinned is True


@pytest.mark.anyio
async def test_unpin_conversation(auth_client, db_session):
    """Toggling pin twice resets is_pinned to False."""
    uid = _user_id(auth_client)
    conv = Conversation(user_id=uid, title="Toggle", is_pinned=True)
    db_session.add(conv)
    await db_session.commit()

    resp = await auth_client.patch(f"/api/conversations/{conv.id}/pin")
    assert resp.status_code == 204
    await db_session.refresh(conv)
    assert conv.is_pinned is False


@pytest.mark.anyio
async def test_pin_nonexistent_conversation_returns_404(auth_client):
    resp = await auth_client.patch(f"/api/conversations/{uuid.uuid4()}/pin")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_pin_wrong_user_returns_404(
    auth_client, second_user_auth_headers, db_session
):
    """User A cannot pin User B's conversation."""
    # Create a conversation owned by second user
    user2_id = _uid_from_headers(second_user_auth_headers)
    conv = Conversation(user_id=user2_id, title="Private")
    db_session.add(conv)
    await db_session.commit()

    # Try to pin as first user (auth_client)
    resp = await auth_client.patch(f"/api/conversations/{conv.id}/pin")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_pinned_conversations_listed_first(auth_client, db_session):
    """List endpoint returns pinned conversations before unpinned ones."""
    uid = _user_id(auth_client)
    normal = Conversation(user_id=uid, title="Normal")
    pinned = Conversation(user_id=uid, title="Pinned", is_pinned=True)
    db_session.add_all([normal, pinned])
    await db_session.commit()

    resp = await auth_client.get("/api/conversations")
    assert resp.status_code == 200
    # Filter to only the two conversations created in this test to avoid
    # interference from other conversations that may exist in the session.
    ids = {str(normal.id), str(pinned.id)}
    ordered = [c for c in resp.json() if c["id"] in ids]
    assert len(ordered) == 2
    assert ordered[0]["id"] == str(pinned.id)


# ---------------------------------------------------------------------------
# Conversation sharing
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_share_conversation_returns_token(auth_client, db_session):
    """POST /share returns a non-empty token."""
    uid = _user_id(auth_client)
    conv = Conversation(user_id=uid, title="Shareable")
    db_session.add(conv)
    await db_session.commit()

    resp = await auth_client.post(f"/api/conversations/{conv.id}/share")
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert len(data["token"]) > 10


@pytest.mark.anyio
async def test_share_twice_returns_same_token(auth_client, db_session):
    """Sharing the same conversation twice returns the existing token."""
    uid = _user_id(auth_client)
    conv = Conversation(user_id=uid, title="Re-share")
    db_session.add(conv)
    await db_session.commit()

    resp1 = await auth_client.post(f"/api/conversations/{conv.id}/share")
    resp2 = await auth_client.post(f"/api/conversations/{conv.id}/share")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["token"] == resp2.json()["token"]


@pytest.mark.anyio
async def test_share_nonexistent_conversation_returns_404(auth_client):
    resp = await auth_client.post(f"/api/conversations/{uuid.uuid4()}/share")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_share_wrong_user_returns_404(
    auth_client, second_user_auth_headers, db_session
):
    """User A cannot share User B's conversation."""
    # Create a conversation owned by second user
    user2_id = _uid_from_headers(second_user_auth_headers)
    conv = Conversation(user_id=user2_id, title="Private conv")
    db_session.add(conv)
    await db_session.commit()

    # Try to share as first user (auth_client)
    resp = await auth_client.post(f"/api/conversations/{conv.id}/share")
    assert resp.status_code == 404
