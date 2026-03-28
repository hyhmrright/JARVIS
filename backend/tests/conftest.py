import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa
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
async def _suppress_auth_audit_logging():
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
async def _suppress_pat_last_used_update():
    """Mock AsyncSessionLocal in deps to prevent cross-event-loop pool contamination.

    _resolve_pat() uses AsyncSessionLocal (now imported at module level in deps.py)
    to update last_used_at. Those connections are bound to the calling event loop
    and become invalid in the next test's event loop. Patching
    app.api.deps.AsyncSessionLocal only affects the deps module namespace —
    app.db.session.AsyncSessionLocal (used by get_db) is left intact.
    """
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = MagicMock(return_value=mock_session)
    mock_session.scalar = AsyncMock(return_value=None)
    with patch("app.api.deps.AsyncSessionLocal", return_value=mock_session):
        yield


@pytest.fixture(scope="session")
def setup_tables():
    """使用同步 psycopg2 驱动建表/删表，避免 session 与 function 事件循环交叉引用。"""
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


@pytest.fixture(autouse=True)
async def _suppress_chat_async_session():
    patched_session = MagicMock()
    patched_session.__aenter__ = AsyncMock(return_value=patched_session)
    patched_session.__aexit__ = AsyncMock(return_value=None)
    patched_session.begin = MagicMock(return_value=patched_session)
    patched_session.scalar = AsyncMock(return_value=None)
    _scalars = MagicMock()
    _scalars.all = MagicMock(return_value=[])
    _execute_result = MagicMock()
    _execute_result.scalars = MagicMock(return_value=_scalars)
    patched_session.execute = AsyncMock(return_value=_execute_result)
    patched_session.add = MagicMock()
    patched_session.flush = AsyncMock()
    patched_session.get = AsyncMock(return_value=None)
    with patch("app.api.chat.routes.AsyncSessionLocal", return_value=patched_session):
        yield


@pytest.fixture(autouse=True)
async def _suppress_worker_async_session():
    """Mock AsyncSessionLocal in worker to prevent cross-event-loop pool contamination.

    execute_cron_job() and deliver_webhook() use AsyncSessionLocal directly.
    Those connections bind to the calling event loop and are invalid in the
    next test's event loop, causing asyncpg "another operation is in progress".
    """
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
    with patch("app.worker.AsyncSessionLocal", return_value=mock_session):
        yield


@pytest.fixture(autouse=True)
async def _suppress_user_memory_tool_async_session():
    """Mock AsyncSessionLocal in user_memory_tool to prevent cross-loop contamination.

    The remember/recall tools open AsyncSessionLocal() directly. Those connections
    bind to the calling event loop and are invalid in the next test's event loop,
    causing asyncpg "Future attached to a different loop".
    """
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.commit = AsyncMock()
    _scalars = MagicMock()
    _scalars.all = MagicMock(return_value=[])
    mock_session.scalars = AsyncMock(return_value=_scalars)
    target = "app.tools.user_memory_tool.AsyncSessionLocal"
    with patch(target, return_value=mock_session):
        yield
