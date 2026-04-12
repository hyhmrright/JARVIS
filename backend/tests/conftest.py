# ruff: noqa: E402
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.pool import NullPool

# --- PRE-IMPORT HIJACKING ---

# 1. Disable Rate Limiting globally
patch("slowapi.Limiter.limit", lambda *args, **kwargs: lambda f: f).start()

# 2. Mock background infra
mock_redis = AsyncMock()
patch("redis.asyncio.Redis.from_url", return_value=mock_redis).start()
patch("arq.create_pool", return_value=AsyncMock()).start()
patch("app.scheduler.runner.start_scheduler", AsyncMock()).start()
patch("app.scheduler.runner.stop_scheduler", AsyncMock()).start()
patch("apscheduler.schedulers.asyncio.AsyncIOScheduler.start", MagicMock()).start()

# 3. Hijack isolated_session and AsyncSessionLocal at the source
shared_mock_session = MagicMock()
shared_mock_session.__aenter__ = AsyncMock(return_value=shared_mock_session)
shared_mock_session.__aexit__ = AsyncMock(return_value=None)
shared_mock_session.begin = MagicMock(return_value=shared_mock_session)
shared_mock_session.execute = AsyncMock(return_value=MagicMock())
shared_mock_session.scalars = AsyncMock(
    return_value=MagicMock(all=MagicMock(return_value=[]))
)

mock_isolated = MagicMock()
mock_isolated.__aenter__ = AsyncMock(return_value=shared_mock_session)
mock_isolated.__aexit__ = AsyncMock(return_value=None)

# Pre-patch all modules that import session objects
targets = [
    "app.db.session",
    "app.api.deps",
    "app.worker",
    "app.services.audit",
    "app.services.notifications",
    "app.services.memory_sync",
    "app.scheduler.runner",
    "app.gateway.agent_runner",
    "app.gateway.router",
    "app.tools.cron_tool",
    "app.api.workflows",
    "app.api.chat.routes",
    "app.tools.user_memory_tool",
]

from contextlib import ExitStack

_early_stack = ExitStack()
for t in targets:
    try:
        _early_stack.enter_context(
            patch(f"{t}.isolated_session", return_value=mock_isolated)
        )
        _early_stack.enter_context(
            patch(f"{t}.AsyncSessionLocal", return_value=shared_mock_session)
        )
    except (ImportError, AttributeError):
        pass

# --- NOW WE CAN IMPORT APP ---
from app.db.session import get_db
from app.main import app

try:
    _pw = os.environ["POSTGRES_PASSWORD"]
except KeyError:
    raise RuntimeError("POSTGRES_PASSWORD is required") from None

TEST_DATABASE_URL = f"postgresql+asyncpg://jarvis:{_pw}@localhost:5432/jarvis_test"
_SYNC_DATABASE_URL = f"postgresql+psycopg2://jarvis:{_pw}@localhost:5432/jarvis_test"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_mocks():
    shared_mock_session.reset_mock()
    mock_redis.reset_mock()
    yield


@pytest.fixture(scope="session")
def setup_tables():
    from sqlalchemy import create_engine as sync_create_engine

    from app.db.base import Base

    engine = sync_create_engine(_SYNC_DATABASE_URL, echo=False)
    with engine.begin() as conn:
        conn.execute(
            sa.text("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        )
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


import sqlalchemy as sa


@pytest.fixture(scope="session")
async def engine(setup_tables):
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    yield engine
    await engine.dispose()


from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


@pytest.fixture
async def db_session(engine):
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


@pytest.fixture
async def client(db_session):
    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client(client):
    token = await _register_test_user_helper(client)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
async def auth_headers(client) -> dict:
    token = await _register_test_user_helper(client)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_auth_headers(client, db_session) -> dict:
    from app.core.security import decode_access_token
    from app.db.models import User

    token = await _register_test_user_helper(client)
    user_id = decode_access_token(token)
    await db_session.execute(
        sa.update(User).where(User.id == user_id).values(role="admin")
    )
    await db_session.commit()
    return {"Authorization": f"Bearer {token}"}


async def _register_test_user_helper(client) -> str:
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    data = {"email": email, "password": "password123"}
    resp = await client.post("/api/auth/register", json=data)
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    return resp.json()["access_token"]
