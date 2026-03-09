import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_full_flow(client):
    unique_email = f"e2e_{uuid.uuid4().hex[:8]}@test.com"
    # 1. 注册
    r = await client.post(
        "/api/auth/register", json={"email": unique_email, "password": "pass1234"}
    )
    assert r.status_code == 201
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. 创建对话
    r = await client.post(
        "/api/conversations", json={"title": "E2E Test"}, headers=headers
    )
    assert r.status_code == 201
    conv_id = r.json()["id"]

    # 3. 列出对话
    r = await client.get("/api/conversations", headers=headers)
    assert r.status_code == 200
    assert any(c["id"] == conv_id for c in r.json())

    # 4. 健康检查
    r = await client.get("/health")
    assert r.json() == {"status": "ok"}
