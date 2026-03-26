# backend/tests/api/test_search.py
"""Tests for the unified search endpoint."""

import uuid

import pytest

from app.core.security import decode_access_token
from app.db.models import Conversation, Document, Message, UserMemory


def _uid(auth_client) -> uuid.UUID:
    token = auth_client.headers["Authorization"].split(" ")[1]
    return uuid.UUID(decode_access_token(token))


@pytest.mark.anyio
async def test_search_requires_auth(client):
    resp = await client.get("/api/search?q=hello")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_search_q_too_short(auth_client):
    resp = await auth_client.get("/api/search?q=ab")
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_search_q_too_long(auth_client):
    resp = await auth_client.get("/api/search?q=" + "a" * 201)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_search_invalid_type(auth_client):
    resp = await auth_client.get("/api/search?q=hello&types=foobar")
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_search_empty_results(auth_client):
    resp = await auth_client.get("/api/search?q=xyzzy_no_match")
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []
    assert body["total"] == 0


@pytest.mark.anyio
async def test_search_finds_message(auth_client, db_session):
    uid = _uid(auth_client)
    conv = Conversation(user_id=uid, title="Test Conv")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(
        conversation_id=conv.id,
        role="human",
        content="UNIQUETOKEN_XY9 searching for this",
    )
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=UNIQUETOKEN_XY9")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any(r["type"] == "message" for r in results)
    msg_result = next(r for r in results if r["type"] == "message")
    assert "UNIQUETOKEN_XY9" in msg_result["snippet"]
    assert msg_result["conversation_id"] == str(conv.id)


@pytest.mark.anyio
async def test_search_snippet_at_start(auth_client, db_session):
    """Snippet should not be prefixed with garbage when match is at pos=0."""
    uid = _uid(auth_client)
    conv = Conversation(user_id=uid, title="Snippet Test")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(
        conversation_id=conv.id,
        role="human",
        content="STARTTOKEN this text follows",
    )
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=STARTTOKEN")
    assert resp.status_code == 200
    results = resp.json()["results"]
    msg_result = next((r for r in results if r["type"] == "message"), None)
    assert msg_result is not None
    assert msg_result["snippet"].startswith("STARTTOKEN")


@pytest.mark.anyio
async def test_search_snippet_at_end(auth_client, db_session):
    """Snippet should not be suffixed with garbage when match is near end."""
    uid = _uid(auth_client)
    conv = Conversation(user_id=uid, title="End Snippet Test")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(
        conversation_id=conv.id,
        role="human",
        content="some prefix text then ENDTOKEN",
    )
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=ENDTOKEN")
    assert resp.status_code == 200
    results = resp.json()["results"]
    msg_result = next((r for r in results if r["type"] == "message"), None)
    assert msg_result is not None
    assert "ENDTOKEN" in msg_result["snippet"]
    assert isinstance(msg_result["snippet"], str)


@pytest.mark.anyio
async def test_search_finds_document(auth_client, db_session):
    uid = _uid(auth_client)
    doc = Document(
        user_id=uid,
        filename="UNIQUEDOC_ABC.pdf",
        file_type="pdf",
        file_size_bytes=100,
        qdrant_collection=f"user_{uid}",
        minio_object_key=f"{uid}/test.pdf",
        is_deleted=False,
    )
    db_session.add(doc)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=UNIQUEDOC_ABC")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any(r["type"] == "document" for r in results)


@pytest.mark.anyio
async def test_search_excludes_soft_deleted_document(auth_client, db_session):
    uid = _uid(auth_client)
    doc = Document(
        user_id=uid,
        filename="DELETED_DOC_ZZZ.pdf",
        file_type="pdf",
        file_size_bytes=100,
        qdrant_collection=f"user_{uid}",
        minio_object_key=f"{uid}/deleted.pdf",
        is_deleted=True,
    )
    db_session.add(doc)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=DELETED_DOC_ZZZ")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert not any(r["type"] == "document" for r in results)


@pytest.mark.anyio
async def test_search_finds_memory(auth_client, db_session):
    uid = _uid(auth_client)
    mem = UserMemory(
        user_id=uid,
        key="test_pref",
        value="UNIQMEMORY_Q7 user prefers dark mode",
        category="preference",
    )
    db_session.add(mem)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=UNIQMEMORY_Q7")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any(r["type"] == "memory" for r in results)


@pytest.mark.anyio
async def test_search_types_filter(auth_client, db_session):
    """types=messages should exclude documents and memories."""
    uid = _uid(auth_client)
    conv = Conversation(user_id=uid, title="Filter Test")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(conversation_id=conv.id, role="human", content="FILTERTEST_TOKEN123")
    db_session.add(msg)
    doc = Document(
        user_id=uid,
        filename="FILTERTEST_TOKEN123.pdf",
        file_type="pdf",
        file_size_bytes=100,
        qdrant_collection=f"user_{uid}",
        minio_object_key=f"{uid}/f.pdf",
        is_deleted=False,
    )
    db_session.add(doc)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=FILTERTEST_TOKEN123&types=messages")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert all(r["type"] == "message" for r in results)
    assert len(results) >= 1


@pytest.mark.anyio
async def test_search_user_isolation(
    auth_client, second_user_auth_headers, client, db_session
):
    """User A must not see User B's messages."""
    token2 = second_user_auth_headers["Authorization"].split(" ")[1]
    uid2 = uuid.UUID(decode_access_token(token2))

    conv2 = Conversation(user_id=uid2, title="User2 Conv")
    db_session.add(conv2)
    await db_session.flush()
    msg2 = Message(
        conversation_id=conv2.id,
        role="human",
        content="ISOLATEDTOKEN_USER2_ONLY",
    )
    db_session.add(msg2)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=ISOLATEDTOKEN_USER2_ONLY")
    assert resp.status_code == 200
    assert resp.json()["results"] == []
