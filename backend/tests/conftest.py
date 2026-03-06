import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine as sync_create_engine
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
def _suppress_auth_audit_logging():
    """Mock audit logging in auth endpoints to prevent cross-event-loop pool issues.

    Each async test gets its own event loop. log_action() acquires connections from
    the module-level AsyncSessionLocal pool; those connections are bound to the calling
    event loop and become invalid in the next test's event loop, causing asyncpg's
    "another operation is in progress" error. Suppressing the call here prevents pool
    contamination without affecting the dedicated test_audit.py unit tests.
    """
    with patch("app.api.auth.log_action", AsyncMock(return_value=None)):
        yield


@pytest.fixture(autouse=True)
def _suppress_pat_last_used_update():
    """Mock AsyncSessionLocal at its definition site to prevent pool contamination.

    _resolve_pat() imports AsyncSessionLocal inside the function body from
    app.db.session, so the correct patch target is app.db.session.AsyncSessionLocal
    (not app.api.deps.AsyncSessionLocal, which is never a module attribute).
    Those connections are bound to the calling event loop and become invalid in
    the next test's event loop, causing asyncpg's "another operation is in
    progress" error. Suppressing it here prevents pool contamination without
    affecting the dedicated PAT auth behaviour under test.
    """
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = MagicMock(return_value=mock_session)
    mock_session.scalar = AsyncMock(return_value=None)
    with patch("app.db.session.AsyncSessionLocal", return_value=mock_session):
        yield


@pytest.fixture(scope="session")
def setup_tables():
    """使用同步 psycopg2 驱动建表/删表，避免 session 与 function 事件循环交叉引用。"""
    engine = sync_create_engine(_SYNC_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
async def db_session(setup_tables):
    """每个测试创建独立的 async engine 和事务，结束后回滚，保证测试间互不影响。"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            # Explicitly begin via await (not `async with conn.begin()`) so
            # the AsyncTransaction is not held as a context manager, giving
            # conn.rollback() in the finally block unconditional control over
            # the root transaction regardless of what the session did.
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


@pytest.fixture
async def auth_client(client):
    """已登录的测试客户端（自动注册并获取 token）。"""
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
