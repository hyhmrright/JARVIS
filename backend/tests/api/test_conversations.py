import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def auth_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        resp = await c.post(
            "/api/auth/register",
            json={"email": "conv@test.com", "password": "pass123"},
        )
        token = resp.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


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
