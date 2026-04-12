from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Private globals for lazy initialization
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    """Internal helper to get or create the engine. Facilitates testing."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            # Use NullPool in tests if requested via env, but for now we rely on mocks
        )
    return _engine


def _get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Internal helper to get or create the sessionmaker. Facilitates testing."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(_get_engine(), expire_on_commit=False)
    return _sessionmaker


def __getattr__(name: str) -> Any:
    """Module-level getattr to support legacy engine and session access."""
    if name == "engine":
        return _get_engine()
    if name == "AsyncSessionLocal":
        return _get_sessionmaker()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def get_db() -> AsyncGenerator[AsyncSession]:
    session_factory = _get_sessionmaker()
    async with session_factory() as session:
        yield session


@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
    """Isolated session manager for background tasks."""
    session_factory = _get_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
