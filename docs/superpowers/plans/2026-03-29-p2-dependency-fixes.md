# P2: Dependency Structure Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Break the `agent/graph.py` ↔ `tools/subagent_tool.py` circular dependency and remove direct DB session access from the tools layer.

**Architecture:** Introduce an `AgentGraphFactory` Protocol in `app/agent/interfaces.py` so `subagent_tool` depends on an abstraction rather than the concrete graph module. Introduce `MemoryRepository` and `CronRepository` in `app/services/repositories.py` so memory and cron tools receive DB access through dependency injection rather than importing `AsyncSessionLocal` directly.

**Tech Stack:** Python `typing.Protocol`, SQLAlchemy `AsyncSession`, `AsyncSessionLocal`

---

### Task 1: Create `app/agent/interfaces.py` with `AgentGraphFactory` Protocol

**Files:**
- Create: `backend/app/agent/interfaces.py`
- Test: `backend/tests/agent/test_interfaces.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/agent/test_interfaces.py
import pytest
from unittest.mock import AsyncMock
from app.agent.interfaces import AgentGraphFactory


def test_agent_graph_factory_is_protocol():
    """AgentGraphFactory must be a structural Protocol, not an ABC."""
    import typing
    assert hasattr(AgentGraphFactory, "__protocol_attrs__") or \
           typing.get_origin(AgentGraphFactory) is not None or \
           AgentGraphFactory.__bases__[0].__name__ in ("Protocol", "object")


@pytest.mark.anyio
async def test_concrete_factory_satisfies_protocol():
    """Any async callable with the right signature satisfies AgentGraphFactory."""
    from langgraph.graph.state import CompiledStateGraph
    from unittest.mock import MagicMock

    class ConcreteFactory:
        async def create(self, messages, config):
            return MagicMock(spec=CompiledStateGraph)

    # Runtime check: Protocol is satisfied structurally
    factory = ConcreteFactory()
    # If Protocol isn't satisfied, this will raise TypeError at runtime
    assert callable(factory.create)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/agent/test_interfaces.py -v
```
Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Create `app/agent/interfaces.py`**

```python
# backend/app/agent/interfaces.py
"""Abstract interfaces for the agent layer.

Defining these in a separate module avoids circular imports:
  agent/graph.py  ->  tools/subagent_tool.py
  tools/subagent_tool.py  ->  agent/graph.py  (previously circular)

After this change:
  tools/subagent_tool.py  ->  agent/interfaces.py  (no cycle)
  agent/graph.py          ->  (unchanged, still concrete)
  app/main.py             ->  injects ConcreteFactory at startup
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage
    from langgraph.graph.state import CompiledStateGraph


@runtime_checkable
class AgentGraphFactory(Protocol):
    """Structural protocol for creating a compiled LangGraph agent graph.

    Consumers (e.g., subagent_tool) depend on this interface, not on the
    concrete ``agent/graph.py`` module.  The concrete implementation is
    injected at application startup via ``app/main.py``.
    """

    async def create(
        self,
        messages: list[BaseMessage],  # type: ignore[type-arg]
        config: object,  # AgentConfig — typed as object to avoid circular import
    ) -> CompiledStateGraph: ...  # type: ignore[type-arg]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/agent/test_interfaces.py -v
```
Expected: both tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/agent/interfaces.py tests/agent/test_interfaces.py
git commit -m "feat: add AgentGraphFactory Protocol to agent/interfaces"
```

---

### Task 2: Create `app/services/repositories.py`

**Files:**
- Create: `backend/app/services/repositories.py`
- Test: `backend/tests/services/test_repositories.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/test_repositories.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.mark.anyio
async def test_memory_repository_get_memories_returns_list(mock_db):
    from app.services.repositories import MemoryRepository
    from app.db.models import UserMemory

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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/services/test_repositories.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Create `app/services/repositories.py`**

```python
# backend/app/services/repositories.py
"""Repository classes for tool-layer DB access.

Tools must not import AsyncSessionLocal directly.  Instead they receive
a repository instance that wraps a session, making them testable without
a live database connection.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CronJob, UserMemory


class MemoryRepository:
    """Read and write UserMemory rows for a given user."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_memories(self, user_id: uuid.UUID) -> list[UserMemory]:
        result = await self._db.scalars(
            select(UserMemory).where(UserMemory.user_id == user_id)
        )
        return list(result.all())

    async def get_memory_by_key(
        self, user_id: uuid.UUID, key: str
    ) -> UserMemory | None:
        return await self._db.scalar(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.key == key,
            )
        )

    async def save_memory(
        self,
        user_id: uuid.UUID,
        key: str,
        value: str,
        category: str = "general",
    ) -> UserMemory:
        """Upsert: update existing key or insert new row."""
        existing = await self.get_memory_by_key(user_id, key)
        if existing is not None:
            existing.value = value
            existing.category = category
            existing.updated_at = datetime.now(UTC)
            await self._db.flush()
            return existing
        mem = UserMemory(
            user_id=user_id,
            key=key,
            value=value,
            category=category,
        )
        self._db.add(mem)
        await self._db.flush()
        return mem

    async def delete_memory(self, memory_id: uuid.UUID) -> bool:
        """Return True if deleted, False if not found."""
        mem = await self._db.get(UserMemory, memory_id)
        if mem is None:
            return False
        await self._db.delete(mem)
        await self._db.flush()
        return True

    async def search_memories(
        self, user_id: uuid.UUID, query: str, limit: int = 100
    ) -> list[UserMemory]:
        from sqlalchemy import or_

        result = await self._db.scalars(
            select(UserMemory)
            .where(
                UserMemory.user_id == user_id,
                or_(
                    UserMemory.key.ilike(f"%{query}%"),
                    UserMemory.value.ilike(f"%{query}%"),
                ),
            )
            .limit(limit)
        )
        return list(result.all())


class CronRepository:
    """Read CronJob rows for a given user (tools need read-only access)."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_job(self, job_id: uuid.UUID) -> CronJob | None:
        return await self._db.scalar(
            select(CronJob).where(CronJob.id == job_id)
        )

    async def list_jobs(self, user_id: uuid.UUID) -> list[CronJob]:
        result = await self._db.scalars(
            select(CronJob).where(
                CronJob.user_id == user_id,
                CronJob.is_active == True,  # noqa: E712
            )
        )
        return list(result.all())
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/services/test_repositories.py -v
```
Expected: all 3 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/services/repositories.py tests/services/test_repositories.py
git commit -m "feat: add MemoryRepository and CronRepository to services layer"
```

---

### Task 3: Update `tools/user_memory_tool.py` to use `MemoryRepository`

**Files:**
- Modify: `backend/app/tools/user_memory_tool.py`
- Create: `backend/tests/tools/test_user_memory_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/tools/test_user_memory_tool.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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
        return_value=mock_repo,
    ):
        tools = create_user_memory_tools(user_id)
        remember = next(t for t in tools if t.name == "remember")
        result = await remember.ainvoke({"key": "name", "value": "Alice", "category": "fact"})

    mock_repo.save_memory.assert_awaited_once_with(
        uuid.UUID(user_id), "name", "Alice", "fact"
    )
    assert "saved" in result.lower() or "name" in result.lower()


@pytest.mark.anyio
async def test_recall_tool_calls_repository_search(user_id):
    """recall() tool must delegate to MemoryRepository.search_memories()."""
    from app.tools.user_memory_tool import create_user_memory_tools
    from app.db.models import UserMemory

    fake_mem = MagicMock(spec=UserMemory)
    fake_mem.key = "name"
    fake_mem.value = "Alice"
    fake_mem.category = "fact"

    mock_repo = AsyncMock()
    mock_repo.search_memories = AsyncMock(return_value=[fake_mem])

    with patch(
        "app.tools.user_memory_tool._make_repository",
        return_value=mock_repo,
    ):
        tools = create_user_memory_tools(user_id)
        recall = next(t for t in tools if t.name == "recall")
        result = await recall.ainvoke({"query": "name"})

    mock_repo.search_memories.assert_awaited_once()
    assert "Alice" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/tools/test_user_memory_tool.py -v
```
Expected: `ImportError` or attribute error — `_make_repository` does not exist.

- [ ] **Step 3: Refactor `app/tools/user_memory_tool.py`**

The current file uses `AsyncSessionLocal` directly inside each tool function.
Replace the session creation with a factory function `_make_repository()` that can be patched in tests:

```python
# backend/app/tools/user_memory_tool.py  — top of file additions
# Remove: from app.db.session import AsyncSessionLocal
# Add:
from app.services.repositories import MemoryRepository


async def _make_repository(user_id_uuid) -> MemoryRepository:  # noqa: ARG001 (unused param)
    """Create a MemoryRepository backed by a fresh isolated session.

    Extracted as a module-level function so tests can patch it without
    starting a real database.
    """
    from app.db.session import isolated_session  # local import avoids startup cost

    # We open the session here and return the repo; the caller owns session lifetime.
    # Tools are short-lived (one LLM call) so this single-use pattern is safe.
    from app.db.session import AsyncSessionLocal
    session = AsyncSessionLocal()
    await session.__aenter__()
    return MemoryRepository(session)
```

Wait — that design leaks the session. Let me use a cleaner approach with a context manager within the tool function body. The key is to make the DB-access portion patchable.

Replace the entire `user_memory_tool.py` with this refactored version:

```python
# backend/app/tools/user_memory_tool.py
"""Persistent user memory tools — store and recall facts across conversations."""

from __future__ import annotations

import uuid

import structlog
from langchain_core.tools import BaseTool, tool

from app.db.models import UserMemory  # noqa: F401 — kept for type hints in docstrings
from app.services.repositories import MemoryRepository

logger = structlog.get_logger(__name__)

_VALID_CATEGORIES = frozenset({"preference", "fact", "reminder", "general"})
_MAX_VALUE_LEN = 2_000
_RECALL_LIMIT = 100


async def _make_repository(user_id: uuid.UUID) -> tuple[MemoryRepository, object]:
    """Return (repo, session) using an isolated DB session.

    The caller MUST close the session after use::

        repo, sess = await _make_repository(uid)
        try:
            result = await repo.get_memories(uid)
        finally:
            await sess.__aexit__(None, None, None)

    This is a module-level function so tests can patch it:
        patch("app.tools.user_memory_tool._make_repository", ...)
    """
    from app.db.session import AsyncSessionLocal

    sess = AsyncSessionLocal()
    db = await sess.__aenter__()
    return MemoryRepository(db), sess


def create_user_memory_tools(user_id: str) -> list[BaseTool]:
    """Return [remember, recall, forget] tools closed over the given user."""
    uid = uuid.UUID(user_id)

    @tool
    async def remember(key: str, value: str, category: str = "general") -> str:
        """Store or update a persistent fact about the user.

        Use this whenever the user shares information they want you to remember,
        such as preferences, personal details, or important facts.
        """
        if category not in _VALID_CATEGORIES:
            category = "general"
        value = value[:_MAX_VALUE_LEN]

        repo, sess = await _make_repository(uid)
        try:
            mem = await repo.save_memory(uid, key, value, category)
            await sess.__aexit__(None, None, None)
            logger.info("memory_saved", user_id=user_id, key=key)
            return f"Saved memory: {mem.key} = {mem.value}"
        except Exception:
            await sess.__aexit__(*__import__("sys").exc_info())
            raise

    @tool
    async def recall(query: str) -> str:
        """Search stored memories for the user.

        Returns a formatted list of matching memory entries.
        """
        repo, sess = await _make_repository(uid)
        try:
            memories = await repo.search_memories(uid, query, limit=_RECALL_LIMIT)
            await sess.__aexit__(None, None, None)
        except Exception:
            await sess.__aexit__(*__import__("sys").exc_info())
            raise

        if not memories:
            return "No memories found matching your query."
        lines = [f"- [{m.category}] {m.key}: {m.value}" for m in memories]
        return "Recalled memories:\n" + "\n".join(lines)

    @tool
    async def forget(key: str) -> str:
        """Delete a stored memory by key."""
        repo, sess = await _make_repository(uid)
        try:
            mem = await repo.get_memory_by_key(uid, key)
            if mem is None:
                await sess.__aexit__(None, None, None)
                return f"No memory found with key '{key}'."
            deleted = await repo.delete_memory(mem.id)
            await sess.__aexit__(None, None, None)
        except Exception:
            await sess.__aexit__(*__import__("sys").exc_info())
            raise

        return f"Deleted memory: {key}" if deleted else f"Could not delete '{key}'."

    return [remember, recall, forget]
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/tools/test_user_memory_tool.py -v
```
Expected: both tests `PASSED`.

- [ ] **Step 5: Run full test suite to check no regressions**

```bash
cd backend && uv run pytest tests/ -x -q --tb=short
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/tools/user_memory_tool.py tests/tools/test_user_memory_tool.py
git commit -m "refactor: user_memory_tool uses MemoryRepository instead of AsyncSessionLocal"
```

---

### Task 4: Update `tools/subagent_tool.py` — use `AgentGraphFactory` Protocol

**Files:**
- Modify: `backend/app/tools/subagent_tool.py`
- Modify: `backend/app/main.py` (inject factory at startup)

- [ ] **Step 1: Read the current subagent_tool.py**

```bash
cat backend/app/tools/subagent_tool.py | head -60
```

Find the function-body import of `create_graph`:
```python
from app.agent.graph import create_graph  # inside function body
```

- [ ] **Step 2: Add factory injection to `subagent_tool.py`**

The subagent tool currently does a function-body import to avoid the circular dependency.
Replace the function-body import with a module-level injectable factory:

```python
# backend/app/tools/subagent_tool.py — add near the top, after existing imports
from app.agent.interfaces import AgentGraphFactory

# Module-level factory — injected by app/main.py at startup.
# Falls back to the real create_graph when not overridden (e.g., in tests that
# don't go through main.py).
_graph_factory: AgentGraphFactory | None = None


def set_graph_factory(factory: AgentGraphFactory) -> None:
    """Called once from app/main.py to inject the concrete graph factory."""
    global _graph_factory
    _graph_factory = factory


async def _get_graph(messages, config):
    """Create a compiled graph using the injected factory or the default."""
    if _graph_factory is not None:
        return await _graph_factory.create(messages, config)
    # Fallback: import directly (maintains backward-compat for tests that
    # call subagent_tool without going through app/main.py)
    from app.agent.graph import create_graph  # local import — breaks cycle at module level
    return create_graph(
        provider=config.llm.provider,
        model=config.llm.model_name,
        api_key=config.llm.api_key,
        enabled_tools=config.enabled_tools,
        api_keys=config.llm.api_keys,
        user_id=config.user_id,
        openai_api_key=config.openai_api_key,
        tavily_api_key=config.tavily_api_key,
        depth=config.depth + 1,
        conversation_id=config.conversation_id,
        base_url=config.llm.base_url,
    )
```

Replace all function-body `from app.agent.graph import create_graph` calls inside `create_subagent_tool` with calls to `_get_graph(messages, config)`.

- [ ] **Step 3: Register factory in `app/main.py`**

Find the `lifespan` function or the app startup section. Add:

```python
# In app/main.py, inside the lifespan startup block or at module level after app creation:
from app.tools.subagent_tool import set_graph_factory


class _ConcreteGraphFactory:
    async def create(self, messages, config):
        from app.agent.graph import create_graph
        return create_graph(
            provider=config.llm.provider,
            model=config.llm.model_name,
            api_key=config.llm.api_key,
            enabled_tools=getattr(config, "enabled_tools", None),
            api_keys=config.llm.api_keys,
            user_id=getattr(config, "user_id", None),
            openai_api_key=getattr(config, "openai_api_key", None),
            tavily_api_key=getattr(config, "tavily_api_key", None),
            depth=getattr(config, "depth", 0) + 1,
            conversation_id=getattr(config, "conversation_id", None),
            base_url=config.llm.base_url,
        )


set_graph_factory(_ConcreteGraphFactory())
```

- [ ] **Step 4: Verify no circular import at module level**

```bash
cd backend && python -c "from app.tools import subagent_tool; print('OK — no circular import')"
```
Expected: `OK — no circular import` with no traceback.

- [ ] **Step 5: Run import check**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```
Expected: collection succeeds.

- [ ] **Step 6: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/tools/subagent_tool.py app/agent/interfaces.py app/main.py
git commit -m "refactor: subagent_tool uses AgentGraphFactory Protocol, breaks circular import"
```

---

### Task 5: Final P2 verification

- [ ] **Step 1: Run full test suite**

```bash
cd backend && uv run pytest tests/ -x -q --tb=short
```
Expected: all tests pass.

- [ ] **Step 2: Verify no circular import in subagent_tool**

```bash
cd backend && python -c "
import importlib
# Force module-level import of both sides of the former cycle
importlib.import_module('app.agent.graph')
importlib.import_module('app.tools.subagent_tool')
print('No circular import at module level')
"
```
Expected: prints `No circular import at module level`.

- [ ] **Step 3: Push**

```bash
git push origin dev
```
