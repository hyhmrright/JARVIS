# backend/tests/tools/test_user_memory_tool.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def user_id():
    return str(uuid.uuid4())


@pytest.mark.anyio
async def test_remember_tool_calls_repository_save(user_id):
    """remember() tool must delegate to MemoryRepository.save_memory()."""
    from app.tools.user_memory_tool import create_user_memory_tools

    mock_repo = AsyncMock()
    mock_repo.save_memory = AsyncMock(return_value=MagicMock(key="name", value="Alice"))

    with patch(
        "app.tools.user_memory_tool._make_repository",
        return_value=(mock_repo, AsyncMock()),
    ):
        tools = create_user_memory_tools(user_id)
        remember = next(t for t in tools if t.name == "remember")
        result = await remember.ainvoke(
            {"key": "name", "value": "Alice", "category": "fact"}
        )

    mock_repo.save_memory.assert_awaited_once_with(
        uuid.UUID(user_id), "name", "Alice", "fact"
    )
    assert "saved" in result.lower() or "name" in result.lower()


@pytest.mark.anyio
async def test_recall_tool_calls_repository_search(user_id):
    """recall() tool must delegate to MemoryRepository.search_memories()."""
    from app.db.models import UserMemory
    from app.tools.user_memory_tool import create_user_memory_tools

    fake_mem = MagicMock(spec=UserMemory)
    fake_mem.key = "name"
    fake_mem.value = "Alice"
    fake_mem.category = "fact"

    mock_repo = AsyncMock()
    mock_repo.search_memories = AsyncMock(return_value=[fake_mem])

    with patch(
        "app.tools.user_memory_tool._make_repository",
        return_value=(mock_repo, AsyncMock()),
    ):
        tools = create_user_memory_tools(user_id)
        recall = next(t for t in tools if t.name == "recall")
        result = await recall.ainvoke({"query": "name"})

    mock_repo.search_memories.assert_awaited_once()
    assert "Alice" in result
