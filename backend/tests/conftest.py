# ruff: noqa: E402
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.pool import NullPool

# --- GLOBAL MOCKS ---
# These are used to stub out background infrastructure

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

mock_redis = AsyncMock()
mock_redis.get = AsyncMock(return_value=None)
mock_redis.set = AsyncMock(return_value=True)
mock_redis.close = AsyncMock()

# --- PRE-IMPORT HIJACKING ---
# We patch everything that could start background tasks or threads

patch("redis.asyncio.Redis.from_url", return_value=mock_redis).start()
patch("arq.create_pool", return_value=AsyncMock()).start()
patch("app.scheduler.runner.start_scheduler", AsyncMock()).start()
patch("app.scheduler.runner.stop_scheduler", AsyncMock()).start()
patch("apscheduler.schedulers.asyncio.AsyncIOScheduler.start", MagicMock()).start()

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
def reset_mocks():
    """Reset mocks before each test."""
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
    yield


@pytest.fixture(scope="session")
def setup_tables():
    """Create tables using a sync engine to avoid loop issues."""
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
    """
    Session-scoped engine. This is the KEY FIX for different-loop errors.
    By using a single engine created in the session loop, we avoid pool contamination.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    """Fresh session per test using the session-scoped engine."""
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
    """Override get_db to use our test session."""

    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client(client):
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123"}
    )
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
async def auth_headers(client) -> dict:
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_auth_headers(client, db_session) -> dict:
    from app.core.security import decode_access_token
    from app.db.models import User

    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123"}
    )
    token = resp.json()["access_token"]
    user_id = decode_access_token(token)
    await db_session.execute(
        sa.update(User).where(User.id == user_id).values(role="admin")
    )
    await db_session.commit()
    return {"Authorization": f"Bearer {token}"}
