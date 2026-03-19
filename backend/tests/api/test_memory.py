"""Tests for the user memory API."""

import uuid

import pytest

from app.core.security import decode_access_token
from app.db.models import UserMemory


async def _user_id(auth_client):
    token = auth_client.headers["Authorization"].split(" ")[1]
    return decode_access_token(token)


@pytest.mark.anyio
async def test_list_memories_empty(auth_client):
    resp = await auth_client.get("/api/memories")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_list_memories_returns_user_memories(auth_client, db_session):
    uid = await _user_id(auth_client)
    db_session.add(UserMemory(user_id=uid, key="name", value="Alice", category="fact"))
    db_session.add(
        UserMemory(user_id=uid, key="lang", value="Python", category="preference")
    )
    await db_session.commit()

    resp = await auth_client.get("/api/memories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    keys = {m["key"] for m in data}
    assert keys == {"name", "lang"}


@pytest.mark.anyio
async def test_delete_memory(auth_client, db_session):
    uid = await _user_id(auth_client)
    mem = UserMemory(user_id=uid, key="to_delete", value="bye", category="general")
    db_session.add(mem)
    await db_session.commit()

    resp = await auth_client.delete(f"/api/memories/{mem.id}")
    assert resp.status_code == 204

    remaining = await auth_client.get("/api/memories")
    assert all(m["key"] != "to_delete" for m in remaining.json())


@pytest.mark.anyio
async def test_delete_memory_not_found(auth_client):
    resp = await auth_client.delete(f"/api/memories/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_clear_all_memories(auth_client, db_session):
    uid = await _user_id(auth_client)
    db_session.add(UserMemory(user_id=uid, key="a", value="1", category="general"))
    db_session.add(UserMemory(user_id=uid, key="b", value="2", category="general"))
    await db_session.commit()

    resp = await auth_client.delete("/api/memories")
    assert resp.status_code == 204

    remaining = await auth_client.get("/api/memories")
    assert remaining.json() == []


@pytest.mark.anyio
async def test_memories_isolated_between_users(
    auth_client, second_user_auth_headers, db_session
):
    token2 = second_user_auth_headers["Authorization"].split(" ")[1]
    uid2 = decode_access_token(token2)
    db_session.add(
        UserMemory(user_id=uid2, key="secret", value="user2_only", category="fact")
    )
    await db_session.commit()

    # First user should not see second user's memories
    resp = await auth_client.get("/api/memories")
    assert all(m["key"] != "secret" for m in resp.json())
