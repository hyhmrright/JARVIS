import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import User, UserSettings

TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def session():
    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s


async def test_create_user(session):
    user = User(email="test@example.com", password_hash="hashed")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    assert user.id is not None
    assert user.is_active is True


async def test_user_has_settings_cascade(session):
    user = User(email="a@b.com", password_hash="x")
    settings = UserSettings(user=user)
    session.add(user)
    await session.commit()
    assert settings.model_provider == "deepseek"
