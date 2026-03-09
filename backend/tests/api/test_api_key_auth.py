import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key, hash_api_key
from app.db.models import ApiKey, User


@pytest.mark.asyncio
async def test_api_key_authentication(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # 1. 创建测试用户
    email = f"auth_test_{uuid.uuid4().hex[:8]}@example.com"
    user = User(email=email, password_hash="hash")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 2. 生成并存储 API Key
    raw_token = generate_api_key()
    api_key = ApiKey(
        user_id=user.id,
        name="Auth Test Key",
        key_hash=hash_api_key(raw_token),
        prefix=raw_token[:8],
        scope="full",
    )
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)

    # 3. 使用 API Key 访问受保护端点 (list_keys)
    headers = {"Authorization": f"Bearer {raw_token}"}
    response = await client.get("/api/keys", headers=headers)

    assert response.status_code == 200
    keys = response.json()
    assert len(keys) >= 1
    assert any(k["name"] == "Auth Test Key" for k in keys)


@pytest.mark.asyncio
async def test_invalid_api_key(client: AsyncClient) -> None:
    headers = {"Authorization": "Bearer jv_invalid_key_12345"}
    response = await client.get("/api/keys", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


@pytest.mark.asyncio
async def test_expired_api_key(client: AsyncClient, db_session: AsyncSession) -> None:
    from datetime import UTC, datetime, timedelta

    # 创建用户
    user = User(
        email=f"expired_test_{uuid.uuid4().hex[:8]}@example.com", password_hash="hash"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 创建已过期 Key
    raw_token = generate_api_key()
    api_key = ApiKey(
        user_id=user.id,
        name="Expired Key",
        key_hash=hash_api_key(raw_token),
        prefix=raw_token[:8],
        scope="full",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.add(api_key)
    await db_session.commit()

    headers = {"Authorization": f"Bearer {raw_token}"}
    response = await client.get("/api/keys", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "API key expired"
