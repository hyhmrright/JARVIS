# backend/tests/services/test_repositories.py
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.mark.anyio
async def test_memory_repository_get_memories_returns_list(mock_db):
    from app.db.models import UserMemory
    from app.services.repositories import MemoryRepository

    user_id = uuid.uuid4()
    fake_memory = MagicMock(spec=UserMemory)
    mock_db.scalars = AsyncMock(return_value=MagicMock(all=lambda: [fake_memory]))

    repo = MemoryRepository(mock_db)
    result = await repo.get_memories(user_id)
    assert result == [fake_memory]


@pytest.mark.anyio
async def test_memory_repository_save_memory_adds_to_session(mock_db):
    from app.services.repositories import MemoryRepository

    user_id = uuid.uuid4()
    mock_db.flush = AsyncMock()
    # get_memory_by_key returns None (new key)
    mock_db.scalar = AsyncMock(return_value=None)

    repo = MemoryRepository(mock_db)
    mem = await repo.save_memory(user_id, "key", "value", "general")

    mock_db.add.assert_called_once()
    mock_db.flush.assert_awaited_once()
    assert mem.user_id == user_id
    assert mem.key == "key"


@pytest.mark.anyio
async def test_cron_repository_get_job_returns_none_when_missing(mock_db):
    from app.services.repositories import CronRepository

    mock_db.scalar = AsyncMock(return_value=None)

    repo = CronRepository(mock_db)
    result = await repo.get_job(uuid.uuid4())
    assert result is None


@pytest.mark.anyio
async def test_memory_repository_delete_memory_returns_true_when_found(mock_db):
    from app.db.models import UserMemory
    from app.services.repositories import MemoryRepository

    mem_id = uuid.uuid4()
    fake_mem = MagicMock(spec=UserMemory)
    mock_db.get = AsyncMock(return_value=fake_mem)
    mock_db.delete = AsyncMock()
    mock_db.flush = AsyncMock()

    repo = MemoryRepository(mock_db)
    result = await repo.delete_memory(mem_id)

    assert result is True
    mock_db.delete.assert_awaited_once_with(fake_mem)


@pytest.mark.anyio
async def test_memory_repository_delete_memory_returns_false_when_not_found(mock_db):
    from app.services.repositories import MemoryRepository

    mock_db.get = AsyncMock(return_value=None)

    repo = MemoryRepository(mock_db)
    result = await repo.delete_memory(uuid.uuid4())

    assert result is False
    mock_db.delete.assert_not_awaited()
