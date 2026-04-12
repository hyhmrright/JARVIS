# ruff: noqa: E402
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.pool import NullPool

# --- PRE-IMPORT HIJACKING ---
# We must ensure all background infra uses mocks BEFORE any app code is imported.

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

# 3. Hijack Redis and ARQ source
mock_redis = AsyncMock()
patch("redis.asyncio.Redis.from_url", return_value=mock_redis).start()
patch("arq.create_pool", return_value=AsyncMock()).start()

# 4. Hijack Scheduler and Worker Threads
patch("app.scheduler.runner.start_scheduler", AsyncMock()).start()
patch("app.scheduler.runner.stop_scheduler", AsyncMock()).start()
patch("apscheduler.schedulers.asyncio.AsyncIOScheduler.start", MagicMock()).start()

# 5. Hijack SQLAlchemy source getters
import app.db.session

patch("app.db.session._get_engine", return_value=AsyncMock()).start()
patch("app.db.session._get_sessionmaker", return_value=lambda: mock_session).start()
# CRITICAL: Overwrite the exported isolated_session at module level
app.db.session.isolated_session = MagicMock(return_value=mock_isolated)

# --- NOW WE CAN IMPORT APP ---
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine as sync_create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.limiter import limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# --- PERMANENT OVERRIDES ---
# These overrides stay active for the entire pytest process to prevent
# background tasks from leaking into real DB/Redis code after a test finishes.


async def _permanent_override_get_db():
    yield mock_session


async def _permanent_override_redis():
    yield mock_redis


app.dependency_overrides[get_db] = _permanent_override_get_db

try:
    from app.api.export import _get_redis as export_get_redis
    from app.api.gateway import _get_redis as gateway_get_redis

    app.dependency_overrides[gateway_get_redis] = _permanent_override_redis
    app.dependency_overrides[export_get_redis] = _permanent_override_redis
except ImportError:
    pass

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
    """测试期间禁用频率限制。"""
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(autouse=True)
def reset_global_mocks():
    """每个测试重置 Mock 对象状态。"""
    mock_session.reset_mock()
    mock_redis.reset_mock()
    yield


@pytest.fixture(scope="session")
def setup_tables():
    """使用同步驱动初始化测试表。"""
    engine = sync_create_engine(_SYNC_DATABASE_URL, echo=False)
    with engine.begin() as conn:
        conn.execute(
            sa.text("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        )
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture
async def db_session(setup_tables):
    """为需要真实数据库操作的测试提供隔离的 session。"""
    # Use NullPool and ensure cleanup to prevent cross-loop issues
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
    """测试 HTTP 客户端。
    默认情况下，它会临时覆盖 get_db 以使用真实的测试数据库。
    """

    async def _temp_override_db():
        yield db_session

    app.dependency_overrides[get_db] = _temp_override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    # Revert back to permanent mock override
    app.dependency_overrides[get_db] = _permanent_override_get_db


async def _register_test_user(client) -> str:
    """注册测试用户。"""
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture
async def auth_client(client):
    token = await _register_test_user(client)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
async def auth_headers(client) -> dict:
    token = await _register_test_user(client)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_auth_headers(client, db_session) -> dict:
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
    token = await _register_test_user(client)
    return {"Authorization": f"Bearer {token}"}
