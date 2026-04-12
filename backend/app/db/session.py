import os
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# In CI/Test environments, we disable pooling entirely to prevent
# "Future attached to a different loop" errors during high-concurrency tests.
_engine_args: dict[str, Any] = {}
if os.getenv("CI") or os.getenv("PYTEST_CURRENT_TEST"):
    _engine_args["poolclass"] = NullPool

engine = create_async_engine(settings.database_url, echo=False, **_engine_args)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
    """Isolated session manager for background tasks."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
