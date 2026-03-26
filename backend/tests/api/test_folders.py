"""Tests for the conversation folders API."""

import uuid

import pytest

from app.core.security import decode_access_token
from app.db.models import ConversationFolder


async def _user_id(auth_client):
    token = auth_client.headers["Authorization"].split(" ")[1]
    return decode_access_token(token)


@pytest.mark.anyio
async def test_list_folders_empty(auth_client):
    resp = await auth_client.get("/api/folders")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_create_folder(auth_client):
    resp = await auth_client.post("/api/folders", json={"name": "Work"})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["name"] == "Work"
    assert data["color"] is None


@pytest.mark.anyio
async def test_create_and_list_folders(auth_client):
    await auth_client.post("/api/folders", json={"name": "Alpha"})
    await auth_client.post("/api/folders", json={"name": "Beta"})

    resp = await auth_client.get("/api/folders")
    assert resp.status_code == 200
    names = {f["name"] for f in resp.json()}
    assert {"Alpha", "Beta"} <= names


@pytest.mark.anyio
async def test_delete_folder(auth_client):
    create_resp = await auth_client.post("/api/folders", json={"name": "ToDelete"})
    folder_id = create_resp.json()["id"]

    del_resp = await auth_client.delete(f"/api/folders/{folder_id}")
    assert del_resp.status_code == 204

    list_resp = await auth_client.get("/api/folders")
    ids = [f["id"] for f in list_resp.json()]
    assert folder_id not in ids


@pytest.mark.anyio
async def test_delete_folder_not_found(auth_client):
    resp = await auth_client.delete(f"/api/folders/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_folder_color_validation(auth_client):
    resp = await auth_client.post(
        "/api/folders", json={"name": "BadColor", "color": "not-a-color"}
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_folder_valid_color(auth_client):
    resp = await auth_client.post(
        "/api/folders", json={"name": "Colored", "color": "#ff0000"}
    )
    assert resp.status_code == 201
    assert resp.json()["color"] == "#ff0000"


@pytest.mark.anyio
async def test_folder_display_order(auth_client, db_session):
    uid = await _user_id(auth_client)
    folder = ConversationFolder(user_id=uid, name="Ordered", display_order=5)
    db_session.add(folder)
    await db_session.commit()

    resp = await auth_client.get("/api/folders")
    found = next((f for f in resp.json() if f["name"] == "Ordered"), None)
    assert found is not None
    assert found["display_order"] == 5


@pytest.mark.anyio
async def test_update_folder(auth_client):
    create_resp = await auth_client.post("/api/folders", json={"name": "Original"})
    folder_id = create_resp.json()["id"]

    patch_resp = await auth_client.patch(
        f"/api/folders/{folder_id}", json={"name": "Renamed", "color": "#00ff00"}
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["name"] == "Renamed"
    assert data["color"] == "#00ff00"
