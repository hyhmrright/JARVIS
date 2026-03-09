import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.models import ApiKey, User


@pytest.mark.asyncio
async def test_api_key_crud_flow(client: AsyncClient, db_session: AsyncSession) -> None:
    # 1. 创建并登录测试用户
    email = f"api_test_{uuid.uuid4().hex[:8]}@example.com"
    user = User(email=email, password_hash="hash")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    # 2. 创建 API Key
    payload = {"name": "Test CRUD Key", "scope": "readonly"}
    response = await client.post("/api/keys", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test CRUD Key"
    assert data["scope"] == "readonly"
    assert "raw_key" in data
    assert data["raw_key"].startswith("jv_")
    key_id = data["id"]

    # 3. 列举 API Keys
    response = await client.get("/api/keys", headers=headers)
    assert response.status_code == 200
    keys = response.json()
    assert len(keys) >= 1
    assert any(k["id"] == key_id for k in keys)
    assert "raw_key" not in keys[0]  # 列表不应包含原始密钥

    # 4. 删除 API Key
    response = await client.delete(f"/api/keys/{key_id}", headers=headers)
    assert response.status_code == 204

    # 5. 验证已删除
    stmt = select(ApiKey).where(ApiKey.id == uuid.UUID(key_id))
    result = await db_session.scalar(stmt)
    assert result is None

@pytest.mark.asyncio
async def test_api_key_limit(client: AsyncClient, db_session: AsyncSession) -> None:
    # 创建用户
    user = User(
        email=f"limit_test_{uuid.uuid4().hex[:8]}@example.com", password_hash="hash"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    # 创建 10 个 Key
    for i in range(10):
        await client.post("/api/keys", json={"name": f"Key {i}"}, headers=headers)

    # 尝试创建第 11 个，应返回 409
    response = await client.post("/api/keys", json={"name": "Key 11"}, headers=headers)
    assert response.status_code == 409
    assert "Maximum" in response.json()["detail"]
