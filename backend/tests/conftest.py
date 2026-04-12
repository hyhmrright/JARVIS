# ruff: noqa: E402
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.pool import NullPool

# --- PRE-IMPORT HIJACKING ---
# We must ensure app.db.session and Redis use mocks BEFORE app.main imports them.

# 1. Create a very robust mock session
mock_session = MagicMock()
mock_session.__aenter__ = AsyncMock(return_value=mock_session)
mock_session.__aexit__ = AsyncMock(return_value=None)
mock_session.begin = MagicMock(return_value=mock_session)
mock_session.scalar = AsyncMock(return_value=None)
mock_session.execute = AsyncMock(return_value=MagicMock())
mock_session.get = AsyncMock(return_value=None)
mock_session.add = MagicMock()
mock_session.flush = AsyncMock()
mock_session.commit = AsyncMock()
mock_session.rollback = AsyncMock()
mock_session.close = AsyncMock()
mock_session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

# 2. Create a mock for isolated_session
mock_isolated = MagicMock()
mock_isolated.__aenter__ = AsyncMock(return_value=mock_session)
mock_isolated.__aexit__ = AsyncMock(return_value=None)

# 3. Hijack Redis
mock_redis = AsyncMock()
mock_redis.get = AsyncMock(return_value=None)
mock_redis.set = AsyncMock(return_value=True)
mock_redis.setex = AsyncMock(return_value=True)
mock_redis.delete = AsyncMock(return_value=1)
mock_redis.getdel = AsyncMock(return_value=None)
mock_redis.close = AsyncMock()

patch("redis.asyncio.Redis.from_url", return_value=mock_redis).start()

# 4. Hijack arq.create_pool
mock_arq = AsyncMock()
patch("arq.create_pool", return_value=mock_arq).start()

# 5. Hijack app.db.session members
import app.db.session

patch("app.db.session._get_engine", return_value=AsyncMock()).start()
patch("app.db.session._get_sessionmaker", return_value=lambda: mock_session).start()
patch("app.db.session.isolated_session", return_value=mock_isolated).start()

# --- NOW WE CAN IMPORT APP ---
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.limiter import limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app

try:
    _pg_password = os.environ["POSTGRES_PASSWORD"]
except KeyError:
    raise RuntimeError(
        "POSTGRES_PASSWORD env var is required to run tests. "
        "Run 'bash scripts/init-env.sh' or export it manually."
    ) from None

TEST_DATABASE_URL = (
    f"postgresql+asyncpg://jarvis:{_pg_password}@localhost:5432/jarvis_test"
)
_SYNC_DATABASE_URL = (
    f"postgresql+psycopg2://jarvis:{_pg_password}@localhost:5432/jarvis_test"
)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """测试期间禁用频率限制，避免多次注册请求触发 429。"""
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(autouse=True)
def reset_global_mocks():
    """Reset the global mock objects before each test."""
    mock_session.reset_mock()
    mock_session.add.reset_mock()
    mock_session.flush.reset_mock()
    mock_session.commit.reset_mock()
    mock_session.rollback.reset_mock()
    mock_session.get.reset_mock()
    mock_session.execute.reset_mock()
    mock_session.scalar.reset_mock()
    mock_session.scalars.reset_mock()
    mock_redis.reset_mock()
    mock_arq.reset_mock()
    yield


@pytest.fixture(autouse=True)
def _global_dependency_overrides():
    """Override FastAPI dependencies globally."""
    from app.api.export import _get_redis as export_get_redis
    from app.api.gateway import _get_redis as gateway_get_redis

    async def _override_redis():
        yield mock_redis

    app.dependency_overrides[gateway_get_redis] = _override_redis
    app.dependency_overrides[export_get_redis] = _override_redis
    yield
    app.dependency_overrides.pop(gateway_get_redis, None)
    app.dependency_overrides.pop(export_get_redis, None)


@pytest.fixture(scope="session")
def setup_tables():
    """使用同步 psycopg2 驱动建表/删表，避免 session 与 function 事件循环交叉引用。"""
    from sqlalchemy import create_engine as sync_create_engine

    engine = sync_create_engine(_SYNC_DATABASE_URL, echo=False)
    with engine.begin() as conn:
        conn.execute(
            sa.text("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        )  # noqa: E501
    Base.metadata.create_all(engine)
    yield
    with engine.begin() as conn:
        conn.execute(
            sa.text("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        )  # noqa: E501
    engine.dispose()


@pytest.fixture
async def db_session(setup_tables):
    """每个测试创建独立的 async engine 和事务，结束后回滚，保证测试间互不影响。"""
    # Use NullPool to force a fresh connection and NO pooling across tests
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.begin()
            session = AsyncSession(
                bind=conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            try:
                yield session
            finally:
                await session.close()
                await conn.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
async def client(db_session):
    """提供已配置好的测试 HTTP 客户端，注入测试 DB session。"""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


async def _register_test_user(client) -> str:
    """Register a test user and return their access token."""
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture
async def auth_client(client):
    """已登录的测试客户端（自动注册并获取 token）。"""
    token = await _register_test_user(client)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
async def auth_headers(client) -> dict:
    """返回已认证用户的 Authorization 请求头。"""
    token = await _register_test_user(client)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_auth_headers(client, db_session) -> dict:
    """Auth headers for an admin user (role promoted to 'admin' in test DB)."""
    from app.core.security import decode_access_token
    from app.db.models import User

    token = await _register_test_user(client)
    user_id = decode_access_token(token)
    await db_session.execute(
        sa.update(User).where(User.id == user_id).values(role="admin")
    )
    await db_session.commit()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def second_user_auth_headers(client) -> dict:
    """Auth headers for a second (non-admin) user."""
    token = await _register_test_user(client)
    return {"Authorization": f"Bearer {token}"}
