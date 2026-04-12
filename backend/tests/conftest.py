# ruff: noqa: E402
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.pool import NullPool

# --- INFRASTRUCTURE MOCKS ---


@pytest.fixture(scope="session", autouse=True)
def mock_infra():
    """Mock background infrastructure for the entire session."""
    # Note: Rate limiter is already disabled in app/core/limiter.py for tests
    with (
        patch("app.infra.qdrant.get_qdrant_client", AsyncMock()),
        patch("app.infra.minio.get_minio_client", MagicMock()),
        patch("redis.asyncio.Redis.from_url", return_value=AsyncMock()),
        patch("arq.create_pool", return_value=AsyncMock()),
        patch("app.scheduler.runner.start_scheduler", AsyncMock()),
        patch("app.scheduler.runner.stop_scheduler", AsyncMock()),
        patch("apscheduler.schedulers.asyncio.AsyncIOScheduler.start", MagicMock()),
    ):
        yield


# --- APP AND DB FIXTURES ---

from app.db.session import get_db
from app.main import create_app


@pytest.fixture
def app():
    """
    FRESH app instance per test. This is the ultimate isolation
    to prevent cross-event-loop contamination from shared FastAPI state.
    """
    _app = create_app()
    _app.router.lifespan_context = MagicMock()
    # Mock load_all_plugins if needed by legacy tests
    if not hasattr(_app, "load_all_plugins"):
        _app.load_all_plugins = MagicMock()
    return _app


@pytest.fixture(scope="session")
def setup_tables():
    from sqlalchemy import create_engine as sync_create_engine

    from app.db.base import Base

    try:
        _pw = os.environ["POSTGRES_PASSWORD"]
    except KeyError:
        raise RuntimeError("POSTGRES_PASSWORD is required") from None

    sync_url = f"postgresql+psycopg2://jarvis:{_pw}@localhost:5432/jarvis_test"
    engine = sync_create_engine(sync_url, echo=False)
    with engine.begin() as conn:
        conn.execute(
            sa.text("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        )
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


@pytest.fixture(scope="session")
async def engine(setup_tables):
    try:
        _pw = os.environ["POSTGRES_PASSWORD"]
    except KeyError:
        raise RuntimeError("POSTGRES_PASSWORD is required") from None

    test_url = f"postgresql+asyncpg://jarvis:{_pw}@localhost:5432/jarvis_test"
    # NullPool is default in CI now via app/db/session.py refactor
    engine = create_async_engine(test_url, echo=False, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    async with engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )

        m_iso = MagicMock()
        m_iso.__aenter__ = AsyncMock(return_value=session)
        m_iso.__aexit__ = AsyncMock(return_value=None)

        # Local override per test
        with (
            patch("app.db.session.AsyncSessionLocal", return_value=session),
            patch("app.db.session.isolated_session", return_value=m_iso),
        ):
            try:
                yield session
            finally:
                await session.close()
                await conn.rollback()


@pytest.fixture
async def client(app, db_session):
    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _register_test_user(client) -> str:
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    data = {"email": email, "password": "password123"}
    resp = await client.post("/api/auth/register", json=data)
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
