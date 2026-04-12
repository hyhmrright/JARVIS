# ruff: noqa: E402
import os
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


# 2. Global placeholders that will be updated per-test
current_mock_session = _make_mock_session()
current_mock_redis = AsyncMock()

# 3. Hijack Redis and ARQ source
patch("redis.asyncio.Redis.from_url", return_value=current_mock_redis).start()
patch("arq.create_pool", return_value=AsyncMock()).start()

# 4. Hijack Scheduler
patch("app.scheduler.runner.start_scheduler", AsyncMock()).start()
patch("app.scheduler.runner.stop_scheduler", AsyncMock()).start()
patch("apscheduler.schedulers.asyncio.AsyncIOScheduler.start", MagicMock()).start()

# 5. Hijack SQLAlchemy source getters in app.db.session
import app.db.session

patch("app.db.session._get_engine", return_value=AsyncMock()).start()
patch(
    "app.db.session._get_sessionmaker", return_value=lambda: current_mock_session
).start()

# --- NOW WE CAN IMPORT APP ---
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# --- PERMANENT OVERRIDES ---


async def _permanent_override_get_db():
    yield current_mock_session


async def _permanent_override_redis():
    yield current_mock_redis


app.dependency_overrides[get_db] = _permanent_override_get_db

try:
    from app.api.export import _get_redis as export_get_redis
    from app.api.gateway import _get_redis as gateway_get_redis

    app.dependency_overrides[gateway_get_redis] = _permanent_override_redis
    app.dependency_overrides[export_get_redis] = _permanent_override_redis
except ImportError:
    pass

try:
    _pw = os.environ["POSTGRES_PASSWORD"]
except KeyError:
    raise RuntimeError("POSTGRES_PASSWORD env var is required") from None

TEST_DATABASE_URL = f"postgresql+asyncpg://jarvis:{_pw}@localhost:5432/jarvis_test"
_SYNC_DATABASE_URL = f"postgresql+psycopg2://jarvis:{_pw}@localhost:5432/jarvis_test"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_mocks_and_overrides():
    """Ensure every test gets a fresh set of mocks."""
    global current_mock_session, current_mock_redis

    # Reset the EXISTING ones.
    current_mock_session.reset_mock()
    current_mock_redis.reset_mock()

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


@pytest.fixture
async def db_session(setup_tables):
    # Use NullPool and ensure CLEAN disposal to prevent any cross-loop leaks
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
    async def _temp_override_db():
        yield db_session

    app.dependency_overrides[get_db] = _temp_override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides[get_db] = _permanent_override_get_db
