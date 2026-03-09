import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiKey, User


@pytest.mark.asyncio
async def test_create_api_key(db_session: AsyncSession) -> None:
    # 1. 创建测试用户
    user = User(
        email=f"test_api_key_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        display_name="API Key Tester",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 2. 创建 API Key
    raw_token = "jv_test_token_123"
    key_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    api_key = ApiKey(
        user_id=user.id,
        name="Test Key",
        key_hash=key_hash,
        prefix=raw_token[:8],
        scope="full",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)

    # 3. 验证存储
    result = await db_session.scalar(select(ApiKey).where(ApiKey.id == api_key.id))
    assert result is not None
    assert result.name == "Test Key"
    assert result.key_hash == key_hash
    assert result.prefix == "jv_test_"
    assert result.user_id == user.id


@pytest.mark.asyncio
async def test_api_key_scope_constraint(db_session: AsyncSession) -> None:
    # 创建测试用户
    user = User(
        email=f"test_scope_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 尝试创建无效 scope 的 API Key
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        api_key = ApiKey(
            user_id=user.id,
            name="Invalid Scope Key",
            key_hash="somehash",
            prefix="jv_inv_",
            scope="invalid_scope",  # 违反 CheckConstraint
        )
        db_session.add(api_key)
        await db_session.commit()
