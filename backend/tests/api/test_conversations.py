import uuid

import pytest
from sqlalchemy import select

from app.core.security import decode_access_token
from app.db.models import Conversation, ConversationTag, Message


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
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert len(body["items"]) >= 2
    assert body["total"] >= 2


async def test_list_conversations_pagination(auth_client):
    for i in range(3):
        await auth_client.post("/api/conversations", json={"title": f"Page Conv {i}"})
    resp = await auth_client.get("/api/conversations?limit=2&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["total"] >= 3
    assert body["limit"] == 2
    assert body["offset"] == 0

    resp2 = await auth_client.get("/api/conversations?limit=2&offset=2")
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["offset"] == 2
    # Items from page 2 should differ from page 1
    ids1 = {c["id"] for c in body["items"]}
    ids2 = {c["id"] for c in body2["items"]}
    assert ids1.isdisjoint(ids2)


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
    assert resp.status_code == 200
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
    assert resp.status_code == 200
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
    assert resp.status_code == 200
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
    assert resp.status_code == 200
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
    msgs = resp.json()["items"]
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
    ordered = [c for c in resp.json()["items"] if c["id"] in ids]
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


# ---------------------------------------------------------------------------
# DELETE /conversations/{conv_id}/messages/{msg_id}
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_delete_message_returns_204(auth_client, db_session):
    """Happy path: owner can delete their own message."""
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Del msg test")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(conversation_id=conv.id, role="human", content="to be deleted")
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.delete(f"/api/conversations/{conv.id}/messages/{msg.id}")
    assert resp.status_code == 204

    # Verify message is gone
    remaining = await db_session.scalars(
        select(Message).where(Message.conversation_id == conv.id)
    )
    assert not any(m.id == msg.id for m in remaining.all())


@pytest.mark.anyio
async def test_delete_message_wrong_user_returns_404(
    auth_client, second_user_auth_headers, db_session
):
    """User A cannot delete messages from User B's conversation (IDOR check)."""
    user2_id = _uid_from_headers(second_user_auth_headers)
    conv = Conversation(user_id=user2_id, title="User B conv")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(conversation_id=conv.id, role="human", content="private")
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.delete(f"/api/conversations/{conv.id}/messages/{msg.id}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_message_wrong_conversation_returns_404(auth_client, db_session):
    """msg_id that exists but belongs to a different conversation returns 404."""
    user_id = _user_id(auth_client)
    conv_a = Conversation(user_id=user_id, title="Conv A")
    conv_b = Conversation(user_id=user_id, title="Conv B")
    db_session.add_all([conv_a, conv_b])
    await db_session.flush()
    msg_in_b = Message(conversation_id=conv_b.id, role="human", content="in b")
    db_session.add(msg_in_b)
    await db_session.commit()

    # Try to delete msg_in_b via conv_a's URL
    resp = await auth_client.delete(
        f"/api/conversations/{conv_a.id}/messages/{msg_in_b.id}"
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_nonexistent_message_returns_404(auth_client, db_session):
    """Deleting a message that doesn't exist returns 404."""
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Conv")
    db_session.add(conv)
    await db_session.commit()

    resp = await auth_client.delete(
        f"/api/conversations/{conv.id}/messages/{uuid.uuid4()}"
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_bookmark_toggle(auth_client, db_session):
    """Bookmarking a message toggles is_bookmarked and returns updated message."""
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Bookmark Test")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(conversation_id=conv.id, role="ai", content="Important answer")
    db_session.add(msg)
    await db_session.commit()

    # Toggle ON
    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}/messages/{msg.id}/bookmark"
    )
    assert resp.status_code == 200
    assert resp.json()["is_bookmarked"] is True

    # Toggle OFF
    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}/messages/{msg.id}/bookmark"
    )
    assert resp.status_code == 200
    assert resp.json()["is_bookmarked"] is False


@pytest.mark.anyio
async def test_bookmark_nonexistent_returns_404(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Conv")
    db_session.add(conv)
    await db_session.commit()

    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}/messages/{uuid.uuid4()}/bookmark"
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_list_bookmarked_messages(auth_client, db_session):
    """GET /conversations/bookmarked returns only bookmarked messages."""
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="My Conv")
    db_session.add(conv)
    await db_session.flush()
    bookmarked = Message(
        conversation_id=conv.id, role="ai", content="Starred", is_bookmarked=True
    )
    normal = Message(conversation_id=conv.id, role="ai", content="Not starred")
    db_session.add_all([bookmarked, normal])
    await db_session.commit()

    resp = await auth_client.get("/api/conversations/bookmarked")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert str(bookmarked.id) in ids
    assert str(normal.id) not in ids


@pytest.mark.anyio
async def test_bookmark_wrong_user_returns_404(
    auth_client, second_user_auth_headers, db_session
):
    """User cannot bookmark a message in another user's conversation."""
    user2_id = _uid_from_headers(second_user_auth_headers)
    conv = Conversation(user_id=user2_id, title="Private")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(conversation_id=conv.id, role="ai", content="Secret")
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}/messages/{msg.id}/bookmark"
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_bookmarked_endpoint_excludes_other_user_messages(
    auth_client, second_user_auth_headers, db_session
):
    """GET /bookmarked only returns the current user's bookmarked messages."""
    user2_id = _uid_from_headers(second_user_auth_headers)
    conv2 = Conversation(user_id=user2_id, title="Other User Conv")
    db_session.add(conv2)
    await db_session.flush()
    other_msg = Message(
        conversation_id=conv2.id, role="ai", content="Other", is_bookmarked=True
    )
    db_session.add(other_msg)
    await db_session.commit()

    resp = await auth_client.get("/api/conversations/bookmarked")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert str(other_msg.id) not in ids


@pytest.mark.anyio
async def test_rate_message_thumbs_up(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Rate Test")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(conversation_id=conv.id, role="ai", content="Answer")
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}/messages/{msg.id}/rate",
        json={"rating": 1},
    )
    assert resp.status_code == 200
    assert resp.json()["user_rating"] == 1


@pytest.mark.anyio
async def test_rate_message_clear(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Rate Clear Test")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(conversation_id=conv.id, role="ai", content="Answer", user_rating=1)
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}/messages/{msg.id}/rate",
        json={"rating": None},
    )
    assert resp.status_code == 200
    assert resp.json()["user_rating"] is None


@pytest.mark.anyio
async def test_rate_message_invalid_value(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Rate Invalid")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(conversation_id=conv.id, role="ai", content="Answer")
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}/messages/{msg.id}/rate",
        json={"rating": 5},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_rate_message_wrong_user_returns_404(
    auth_client, second_user_auth_headers, db_session
):
    user2_id = _uid_from_headers(second_user_auth_headers)
    conv = Conversation(user_id=user2_id, title="Private")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(conversation_id=conv.id, role="ai", content="Secret")
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}/messages/{msg.id}/rate",
        json={"rating": 1},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_rate_human_message_returns_404(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Human Msg Test")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(conversation_id=conv.id, role="human", content="My question")
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}/messages/{msg.id}/rate",
        json={"rating": 1},
    )
    assert resp.status_code == 404


# ── Tag tests ─────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_add_and_list_tags(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Tagged Conv")
    db_session.add(conv)
    await db_session.commit()

    resp = await auth_client.post(
        f"/api/conversations/{conv.id}/tags", json={"tag": "work"}
    )
    assert resp.status_code == 201
    assert "work" in resp.json()

    # Tags also appear in the conversation list
    resp = await auth_client.get("/api/conversations")
    found = next((c for c in resp.json()["items"] if c["id"] == str(conv.id)), None)
    assert found is not None
    assert "work" in found["tags"]


@pytest.mark.anyio
async def test_add_tag_normalises_to_lowercase(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Case Test")
    db_session.add(conv)
    await db_session.commit()

    resp = await auth_client.post(
        f"/api/conversations/{conv.id}/tags", json={"tag": "Work"}
    )
    assert resp.status_code == 201
    assert "work" in resp.json()


@pytest.mark.anyio
async def test_add_duplicate_tag_is_idempotent(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Dup Tag")
    db_session.add(conv)
    await db_session.commit()

    await auth_client.post(f"/api/conversations/{conv.id}/tags", json={"tag": "ai"})
    resp = await auth_client.post(
        f"/api/conversations/{conv.id}/tags", json={"tag": "ai"}
    )
    assert resp.status_code == 201
    assert resp.json().count("ai") == 1


@pytest.mark.anyio
async def test_remove_tag(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Remove Tag")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(ConversationTag(conversation_id=conv.id, tag="research"))
    await db_session.commit()

    resp = await auth_client.delete(f"/api/conversations/{conv.id}/tags/research")
    assert resp.status_code == 204

    # Tag gone from conversation list
    resp = await auth_client.get("/api/conversations")
    found = next((c for c in resp.json()["items"] if c["id"] == str(conv.id)), None)
    assert found is not None
    assert "research" not in found["tags"]


@pytest.mark.anyio
async def test_remove_nonexistent_tag_returns_404(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="No Tag")
    db_session.add(conv)
    await db_session.commit()

    resp = await auth_client.delete(f"/api/conversations/{conv.id}/tags/ghost")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_list_user_tags(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv1 = Conversation(user_id=user_id, title="C1")
    conv2 = Conversation(user_id=user_id, title="C2")
    db_session.add_all([conv1, conv2])
    await db_session.flush()
    db_session.add(ConversationTag(conversation_id=conv1.id, tag="alpha"))
    db_session.add(ConversationTag(conversation_id=conv2.id, tag="beta"))
    await db_session.commit()

    resp = await auth_client.get("/api/conversations/tags")
    assert resp.status_code == 200
    tags = resp.json()
    assert "alpha" in tags
    assert "beta" in tags


@pytest.mark.anyio
async def test_add_tag_wrong_user_returns_404(
    auth_client, second_user_auth_headers, db_session
):
    user2_id = _uid_from_headers(second_user_auth_headers)
    conv = Conversation(user_id=user2_id, title="Private")
    db_session.add(conv)
    await db_session.commit()

    resp = await auth_client.post(
        f"/api/conversations/{conv.id}/tags", json={"tag": "secret"}
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_remove_tag_wrong_user_returns_404(
    auth_client, second_user_auth_headers, db_session
):
    user2_id = _uid_from_headers(second_user_auth_headers)
    conv = Conversation(user_id=user2_id, title="Private")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(ConversationTag(conversation_id=conv.id, tag="secret"))
    await db_session.commit()

    resp = await auth_client.delete(f"/api/conversations/{conv.id}/tags/secret")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_list_conversations_includes_tags(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Tag Test Conv")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(ConversationTag(conversation_id=conv.id, tag="mytag"))
    await db_session.commit()

    resp = await auth_client.get("/api/conversations")
    assert resp.status_code == 200
    found = next((c for c in resp.json()["items"] if c["id"] == str(conv.id)), None)
    assert found is not None
    assert "mytag" in found["tags"]


@pytest.mark.anyio
async def test_list_user_tags_excludes_other_users(
    auth_client, second_user_auth_headers, db_session
):
    user2_id = _uid_from_headers(second_user_auth_headers)
    conv2 = Conversation(user_id=user2_id, title="Other User Conv")
    db_session.add(conv2)
    await db_session.flush()
    db_session.add(ConversationTag(conversation_id=conv2.id, tag="other-user-tag"))
    await db_session.commit()

    resp = await auth_client.get("/api/conversations/tags")
    assert resp.status_code == 200
    assert "other-user-tag" not in resp.json()


@pytest.mark.anyio
async def test_add_tag_over_limit_returns_422(auth_client, db_session):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Full Tags Conv")
    db_session.add(conv)
    await db_session.flush()
    db_session.add_all(
        [ConversationTag(conversation_id=conv.id, tag=f"tag{i:02d}") for i in range(20)]
    )
    await db_session.commit()

    resp = await auth_client.post(
        f"/api/conversations/{conv.id}/tags", json={"tag": "overflow"}
    )
    assert resp.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("bad_tag", ["bad tag", "a,b", "", "\ttab", "new\nline"])
async def test_add_invalid_tag_returns_422(auth_client, db_session, bad_tag):
    user_id = _user_id(auth_client)
    conv = Conversation(user_id=user_id, title="Validation Conv")
    db_session.add(conv)
    await db_session.commit()
    resp = await auth_client.post(
        f"/api/conversations/{conv.id}/tags", json={"tag": bad_tag}
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_patch_conversation_persona_id(auth_client):
    """PATCH /conversations/{id} can update persona_id."""
    # Create a persona
    persona_resp = await auth_client.post(
        "/api/personas",
        json={"name": "Test Persona", "system_prompt": "Be brief."},
    )
    assert persona_resp.status_code == 201
    persona_id = persona_resp.json()["id"]

    # Create a conversation
    conv_resp = await auth_client.post(
        "/api/conversations", json={"title": "Test Conv"}
    )
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    # Attach persona
    patch_resp = await auth_client.patch(
        f"/api/conversations/{conv_id}", json={"persona_id": persona_id}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["persona_id"] == persona_id


@pytest.mark.anyio
async def test_export_conversation_markdown_with_header(auth_client, db_session):
    """Export conversation as Markdown includes Exported/Messages header lines."""
    uid = _user_id(auth_client)
    conv = Conversation(user_id=uid, title="Export Test Conv")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(
        Message(conversation_id=conv.id, role="human", content="Hello world")
    )
    db_session.add(Message(conversation_id=conv.id, role="ai", content="Hi there!"))
    await db_session.commit()

    resp = await auth_client.get(f"/api/conversations/{conv.id}/export?format=md")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("content-disposition", "")
    body = resp.text
    assert "Export Test Conv" in body
    assert "Hello world" in body
    assert "Hi there!" in body
    assert "Exported:" in body
    assert "Messages:" in body


@pytest.mark.anyio
async def test_export_conversation_json_truncated_field(auth_client, db_session):
    """JSON export includes truncated field (False when under 1000 messages)."""
    uid = _user_id(auth_client)
    conv = Conversation(user_id=uid, title="JSON Export Truncated")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(Message(conversation_id=conv.id, role="human", content="hi"))
    await db_session.commit()

    resp = await auth_client.get(f"/api/conversations/{conv.id}/export?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert "truncated" in data
    assert data["truncated"] is False  # only 1 message, not truncated
    assert "exported_at" in data
    assert "id" in data["messages"][0]


@pytest.mark.anyio
async def test_export_other_user_conversation_returns_404_cap(
    auth_client, second_user_auth_headers, db_session
):
    """Cannot export another user's conversation (1000-cap version)."""
    user2_id = _uid_from_headers(second_user_auth_headers)
    conv2 = Conversation(user_id=user2_id, title="User2 Private Cap")
    db_session.add(conv2)
    await db_session.commit()

    resp = await auth_client.get(f"/api/conversations/{conv2.id}/export?format=md")
    assert resp.status_code == 404
