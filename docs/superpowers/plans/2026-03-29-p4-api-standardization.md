# P4: API Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate 12 inconsistent pagination definitions and standardize non-SSE database session creation.

**Architecture:** Add `PaginationParams` dependency class to `app/api/deps.py`; add `isolated_session()` context manager to `app/db/session.py`; replace all direct `Query(limit=...)` declarations and non-SSE `AsyncSessionLocal()` calls across the API layer.

**Tech Stack:** FastAPI `Depends`, SQLAlchemy `AsyncSession`, Python `contextlib.asynccontextmanager`

---

### Task 1: Add `isolated_session()` to `app/db/session.py`

**Files:**
- Modify: `backend/app/db/session.py`
- Test: `backend/tests/db/test_session.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/db/test_session.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.anyio
async def test_isolated_session_commits_on_success():
    """isolated_session() must commit the session when no exception is raised."""
    mock_session = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db.session.AsyncSessionLocal", return_value=mock_cm):
        from app.db.session import isolated_session
        async with isolated_session() as db:
            pass  # no exception

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_isolated_session_rolls_back_on_exception():
    """isolated_session() must roll back and re-raise when an exception occurs."""
    mock_session = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db.session.AsyncSessionLocal", return_value=mock_cm):
        from app.db.session import isolated_session
        with pytest.raises(ValueError, match="boom"):
            async with isolated_session() as db:
                raise ValueError("boom")

    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/db/test_session.py -v
```
Expected: `ImportError` or `FAIL` — `isolated_session` does not exist yet.

- [ ] **Step 3: Add `isolated_session` to `app/db/session.py`**

```python
# backend/app/db/session.py  — full file after change
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/db/test_session.py -v
```
Expected: `PASSED` for both tests.

- [ ] **Step 5: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/db/session.py tests/db/test_session.py
git commit -m "feat: add isolated_session() context manager to db/session"
```

---

### Task 2: Add `PaginationParams` to `app/api/deps.py`

**Files:**
- Modify: `backend/app/api/deps.py`
- Test: `backend/tests/api/test_deps.py` (new or extend existing)

- [ ] **Step 1: Write the failing test**

```python
# Add to backend/tests/api/test_deps.py (create file if missing)
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.deps import PaginationParams

def test_pagination_params_defaults():
    params = PaginationParams()
    assert params.skip == 0
    assert params.limit == 50


def test_pagination_params_custom():
    params = PaginationParams(skip=10, limit=20)
    assert params.skip == 10
    assert params.limit == 20


def test_pagination_params_limit_capped():
    """limit above 200 should be rejected by FastAPI Query validation."""
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from typing import Annotated

    app = FastAPI()

    @app.get("/items")
    async def list_items(p: Annotated[PaginationParams, Depends()]):
        return {"skip": p.skip, "limit": p.limit}

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/items?limit=9999")
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/api/test_deps.py::test_pagination_params_defaults -v
```
Expected: `ImportError` — `PaginationParams` not defined yet.

- [ ] **Step 3: Add `PaginationParams` to `app/api/deps.py`**

Add the following class immediately after the `security = HTTPBearer()` line (after the imports, before `ResolvedLLMConfig`):

```python
# Insert after: security = HTTPBearer()
class PaginationParams:
    """Reusable pagination dependency for list endpoints.

    Usage::

        @router.get("/items")
        async def list_items(p: Annotated[PaginationParams, Depends()]):
            return db.query(...).offset(p.skip).limit(p.limit).all()

    Individual routes may override the default ``limit`` by subclassing or
    adding their own ``Query`` parameters — but they should use this class as
    the baseline so all endpoints share the same skip/limit semantics.
    """

    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(50, ge=1, le=200, description="Maximum records to return"),
    ) -> None:
        self.skip = skip
        self.limit = limit
```

Also add `Query` to the existing `from fastapi import ...` import if not already present (it already is based on the file — verify).

- [ ] **Step 4: Run all three tests**

```bash
cd backend && uv run pytest tests/api/test_deps.py -v
```
Expected: all 3 `PASSED`.

- [ ] **Step 5: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/api/deps.py tests/api/test_deps.py
git commit -m "feat: add PaginationParams dependency to api/deps"
```

---

### Task 3: Replace pagination `Query` params in API modules

**Files to modify** (12 locations):
- `backend/app/api/conversations.py` — 3 endpoints
- `backend/app/api/admin.py` — 1 endpoint
- `backend/app/api/cron.py` — 1 endpoint
- `backend/app/api/memory.py` — 1 endpoint
- `backend/app/api/notifications.py` — 1 endpoint
- `backend/app/api/personas.py` — 1 endpoint
- `backend/app/api/search.py` — 1 endpoint
- `backend/app/api/webhooks.py` — 1 endpoint
- `backend/app/api/workflows.py` — 2 endpoints
- `backend/app/api/workspaces.py` — 1 endpoint

- [ ] **Step 1: Update all files — replace pattern**

For each file, replace the individual `skip` and `limit` Query parameters with `PaginationParams`.

**Pattern to find and replace (example from `conversations.py`):**

Before:
```python
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ...
):
    ...
    .offset(skip).limit(limit)
```

After:
```python
from typing import Annotated
from app.api.deps import PaginationParams  # add to imports

async def list_conversations(
    pagination: Annotated[PaginationParams, Depends()],
    ...
):
    ...
    .offset(pagination.skip).limit(pagination.limit)
```

Apply this same pattern to every endpoint listed above. For endpoints with custom max limits (e.g., `conversations.py:426` uses `le=500`), keep the custom limit as an additional explicit `Query` parameter named `limit` and do NOT use `PaginationParams` for that specific endpoint — log a `# NOTE: custom limit` comment.

- [ ] **Step 2: Verify lint passes**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
```
Expected: no errors.

- [ ] **Step 3: Run import check (catches FastAPI route registration errors)**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```
Expected: collection succeeds, no `ImportError`.

- [ ] **Step 4: Commit**

```bash
git add app/api/
git commit -m "refactor: replace scattered pagination Query params with PaginationParams"
```

---

### Task 4: Replace non-SSE `AsyncSessionLocal()` calls with `isolated_session()`

**Files to modify:**
- `backend/app/api/deps.py` line 108 (`_resolve_pat`)
- `backend/app/api/canvas.py`
- `backend/app/api/voice.py` (non-SSE usage only)

**SSE usages to leave untouched** (add explanatory comment):
- `backend/app/api/chat/routes.py` — all `AsyncSessionLocal()` calls inside `generate()` — leave as-is, add `# SSE: fine-grained per-chunk commit, cannot use isolated_session()` comment
- `backend/app/api/workflows.py` — `_update_run_status()` inside SSE generator — leave as-is, same comment

- [ ] **Step 1: Update `_resolve_pat` in `app/api/deps.py`**

Find lines 107–115 in `app/api/deps.py`:

Before:
```python
    async with AsyncSessionLocal() as _session:
        async with _session.begin():
            result = await _session.scalar(
                select(ApiKey).where(ApiKey.id == api_key.id)
            )
            if result is not None:
                result.last_used_at = datetime.now(UTC)
```

After:
```python
    from app.db.session import isolated_session  # local import avoids circular at module load

    async with isolated_session() as _session:
        result = await _session.scalar(
            select(ApiKey).where(ApiKey.id == api_key.id)
        )
        if result is not None:
            result.last_used_at = datetime.now(UTC)
```

Note: `isolated_session()` auto-commits, so `_session.begin()` is not needed.

- [ ] **Step 2: Add SSE comment to `routes.py`**

In `app/api/chat/routes.py`, find each `async with AsyncSessionLocal() as` inside the `generate()` function and add a one-line comment above each:

```python
# SSE: fine-grained per-chunk commit — cannot use isolated_session()
async with AsyncSessionLocal() as persist_sess:
```

Do the same in `app/api/workflows.py` for `_update_run_status()`.

- [ ] **Step 3: Verify lint and import check**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add app/api/deps.py app/api/chat/routes.py app/api/workflows.py
git commit -m "refactor: replace non-SSE AsyncSessionLocal() with isolated_session()"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run full static checks**

```bash
cd backend && uv run ruff check && uv run mypy app
```
Expected: no errors.

- [ ] **Step 2: Run tests**

```bash
cd backend && uv run pytest tests/ -x -q --tb=short
```
Expected: all existing tests pass + 5 new tests pass.

- [ ] **Step 3: Push**

```bash
git push origin dev
```
