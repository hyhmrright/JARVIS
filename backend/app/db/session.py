from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
    """Context manager for a one-off DB session outside FastAPI's dependency injection.

    Use this in background workers, schedulers, and non-SSE route helpers instead of
    calling ``AsyncSessionLocal()`` directly.  Commits on clean exit, rolls back on
    any exception, and always closes the session.

    SSE streaming generators should still call ``AsyncSessionLocal()`` directly —
    they need fine-grained control over individual per-chunk commits and cannot use
    this wrapper.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
