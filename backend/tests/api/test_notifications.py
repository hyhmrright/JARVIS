"""Tests for the notifications API."""

import uuid

import pytest

from app.core.security import decode_access_token
from app.db.models import Notification


def _uid(auth_client):
    token = auth_client.headers["Authorization"].split(" ")[1]
    return uuid.UUID(decode_access_token(token))


def _make_notification(user_id, *, is_read=False):
    return Notification(
        user_id=user_id,
        type="cron_completed",
        title="Job done",
        body="Your cron job finished successfully.",
        is_read=is_read,
        metadata_json={},
    )


@pytest.mark.anyio
async def test_list_notifications_empty(auth_client):
    resp = await auth_client.get("/api/notifications")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_list_notifications_unread_only_by_default(auth_client, db_session):
    uid = _uid(auth_client)
    db_session.add(_make_notification(uid, is_read=False))
    db_session.add(_make_notification(uid, is_read=True))
    await db_session.commit()

    resp = await auth_client.get("/api/notifications")
    assert resp.status_code == 200
    items = resp.json()
    assert all(not n["is_read"] for n in items)
    assert len(items) == 1


@pytest.mark.anyio
async def test_list_notifications_include_read(auth_client, db_session):
    uid = _uid(auth_client)
    db_session.add(_make_notification(uid, is_read=False))
    db_session.add(_make_notification(uid, is_read=True))
    await db_session.commit()

    resp = await auth_client.get("/api/notifications?include_read=true")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.anyio
async def test_mark_notification_read(auth_client, db_session):
    uid = _uid(auth_client)
    notif = _make_notification(uid)
    db_session.add(notif)
    await db_session.commit()

    resp = await auth_client.patch(f"/api/notifications/{notif.id}/read")
    assert resp.status_code == 204

    # Should now be absent from unread list
    list_resp = await auth_client.get("/api/notifications")
    assert all(str(n["id"]) != str(notif.id) for n in list_resp.json())


@pytest.mark.anyio
async def test_mark_all_notifications_read(auth_client, db_session):
    uid = _uid(auth_client)
    db_session.add(_make_notification(uid))
    db_session.add(_make_notification(uid))
    await db_session.commit()

    resp = await auth_client.post("/api/notifications/mark-all-read")
    assert resp.status_code == 204

    list_resp = await auth_client.get("/api/notifications")
    assert list_resp.json() == []


@pytest.mark.anyio
async def test_delete_notification(auth_client, db_session):
    uid = _uid(auth_client)
    notif = _make_notification(uid)
    db_session.add(notif)
    await db_session.commit()

    resp = await auth_client.delete(f"/api/notifications/{notif.id}")
    assert resp.status_code == 204

    list_resp = await auth_client.get("/api/notifications?include_read=true")
    assert all(str(n["id"]) != str(notif.id) for n in list_resp.json())


@pytest.mark.anyio
async def test_delete_all_notifications(auth_client, db_session):
    uid = _uid(auth_client)
    db_session.add(_make_notification(uid))
    db_session.add(_make_notification(uid))
    await db_session.commit()

    resp = await auth_client.delete("/api/notifications")
    assert resp.status_code == 204

    list_resp = await auth_client.get("/api/notifications?include_read=true")
    assert list_resp.json() == []


@pytest.mark.anyio
async def test_delete_notification_not_found(auth_client):
    resp = await auth_client.delete(f"/api/notifications/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_notifications_isolated_between_users(
    auth_client, second_user_auth_headers, client, db_session
):
    token2 = second_user_auth_headers["Authorization"].split(" ")[1]
    uid2 = decode_access_token(token2)
    db_session.add(_make_notification(uid2))
    await db_session.commit()

    # First user must not see second user's notifications
    resp = await auth_client.get("/api/notifications?include_read=true")
    assert resp.status_code == 200
    assert resp.json() == []
