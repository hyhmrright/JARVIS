# ruff: noqa: E402
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.pool import NullPool

# --- PRE-IMPORT HIJACKING ---


# 1. Create a factory for fresh mock sessions per test
def _make_mock_session():
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    mock.begin = MagicMock(return_value=mock)
    mock.scalar = AsyncMock(return_value=None)
    mock.execute = AsyncMock(return_value=MagicMock())
    mock.get = AsyncMock(return_value=None)
    mock.add = MagicMock()
    mock.flush = AsyncMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.close = AsyncMock()
    mock.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    return mock


# Global mock instances
shared_mock_session = _make_mock_session()
shared_mock_isolated = MagicMock()
shared_mock_isolated.__aenter__ = AsyncMock(return_value=shared_mock_session)
shared_mock_isolated.__aexit__ = AsyncMock(return_value=None)

# 2. Apply aggressive module-level patches
from contextlib import ExitStack

_early_stack = ExitStack()

# Hijack Redis and ARQ
_early_stack.enter_context(
    patch("redis.asyncio.Redis.from_url", return_value=AsyncMock())
)
_early_stack.enter_context(patch("arq.create_pool", return_value=AsyncMock()))

# Hijack Scheduler
_early_stack.enter_context(patch("app.scheduler.runner.start_scheduler", AsyncMock()))
_early_stack.enter_context(patch("app.scheduler.runner.stop_scheduler", AsyncMock()))

# Hijack ALL possible isolated_session and AsyncSessionLocal targets
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

for t in targets:
    try:
        _early_stack.enter_context(
            patch(f"{t}.isolated_session", return_value=shared_mock_isolated)
        )
        _early_stack.enter_context(
            patch(f"{t}.AsyncSessionLocal", return_value=shared_mock_session)
        )
    except (ImportError, AttributeError):
        pass

# --- NOW WE CAN IMPORT APP ---
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db.base import Base
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
def reset_shared_mocks():
    """Reset the shared mocks before each test."""
    shared_mock_session.reset_mock()
    shared_mock_session.add.reset_mock()
    shared_mock_session.flush.reset_mock()
    shared_mock_session.commit.reset_mock()
    shared_mock_session.rollback.reset_mock()
    shared_mock_session.get.reset_mock()
    shared_mock_session.execute.reset_mock()
    shared_mock_session.scalar.reset_mock()
    shared_mock_session.scalars.reset_mock()
    yield


@pytest.fixture(scope="session")
def setup_tables():
    from sqlalchemy import create_engine as sync_create_engine

    engine = sync_create_engine(_SYNC_DATABASE_URL, echo=False)
    with engine.begin() as conn:
        conn.execute(
            sa.text("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        )
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture(scope="session")
async def engine(setup_tables):
    # Use session scope for the engine to ensure only one pool exists
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    yield engine
    await engine.dispose()


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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _register_test_user(client) -> str:
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123"}
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
