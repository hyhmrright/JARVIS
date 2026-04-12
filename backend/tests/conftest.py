# ruff: noqa: E402
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.pool import NullPool

# --- GLOBAL INFRA MOCKS ---

patch("app.infra.qdrant.get_qdrant_client", AsyncMock()).start()
patch("app.infra.minio.get_minio_client", MagicMock()).start()
patch("redis.asyncio.Redis.from_url", return_value=AsyncMock()).start()
patch("arq.create_pool", return_value=AsyncMock()).start()
patch("app.scheduler.runner.start_scheduler", AsyncMock()).start()
patch("app.scheduler.runner.stop_scheduler", AsyncMock()).start()

# --- APP FIXTURES ---

from app.core.limiter import limiter
from app.db.session import get_db
from app.main import app

# Disable app lifespan
app.router.lifespan_context = MagicMock()


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """测试期间禁用频率限制。"""
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


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


@pytest.fixture
async def db_session(setup_tables):
    """
    FRESH engine and session per test.
    """
    try:
        _pw = os.environ["POSTGRES_PASSWORD"]
    except KeyError:
        raise RuntimeError("POSTGRES_PASSWORD is required") from None

    test_url = f"postgresql+asyncpg://jarvis:{_pw}@localhost:5432/jarvis_test"
    engine = create_async_engine(test_url, echo=False, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.begin()
            session = AsyncSession(
                bind=conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )

            m_iso = MagicMock()
            m_iso.__aenter__ = AsyncMock(return_value=session)
            m_iso.__aexit__ = AsyncMock(return_value=None)

            # Critical injection
            with (
                patch("app.db.session.AsyncSessionLocal", return_value=session),
                patch("app.db.session.isolated_session", return_value=m_iso),
                patch("app.api.deps.isolated_session", return_value=m_iso),
                patch("app.worker.AsyncSessionLocal", return_value=session),
            ):
                try:
                    yield session
                finally:
                    await session.close()
                    await conn.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
async def client(db_session):
    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
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
