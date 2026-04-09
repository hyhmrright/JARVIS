# Brooks-Lint Architecture Audit Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 9 findings from the Brooks-Lint architecture audit (2 Critical, 3 Warning, 3 Suggestion) to raise the health score from 52/100 to 85+.

**Architecture:** Extract domain services from API handlers, enrich domain models with behavior methods, centralize authorization, remove dead code/middle-man wrappers, fix circular dependencies, consolidate duplicated plugin logic, and rename infrastructure-leaking identifiers.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, pytest, Pydantic

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `backend/app/services/cron_service.py` | CronJob business logic (validation, quota, encryption, scheduler registration) |
| `backend/app/services/workspace_service.py` | Workspace CRUD, membership authorization, settings management |
| `backend/app/services/authorization.py` | Centralized authorization helpers (org check, doc access, workspace role) |
| `backend/tests/services/test_cron_service.py` | Unit tests for CronService |
| `backend/tests/services/test_workspace_service.py` | Unit tests for WorkspaceService |
| `backend/tests/services/test_authorization.py` | Unit tests for authorization helpers |

### Modified Files
| File | Change |
|------|--------|
| `backend/app/api/cron.py` | Thin routes calling CronService |
| `backend/app/api/workspaces.py` | Thin routes calling WorkspaceService |
| `backend/app/api/documents.py` | Move helpers to authorization/service; rename `_get_qdrant_collection` → `get_document_collection` |
| `backend/app/db/models/scheduler.py` | Add `CronJob.create()` factory + `validate_trigger_type()` |
| `backend/app/db/models/organization.py` | Add `Workspace.soft_delete()`, `WorkspaceMember.is_privileged()` |
| `backend/app/infra/redis.py` | DELETE |
| `backend/app/infra/ollama.py` | DELETE |
| `backend/app/main.py` | Replace `_ConcreteGraphFactory` class with simple async function |
| `backend/app/plugins/loader.py` | Extract shared `_safe_extract_zip()` helper |
| `backend/app/plugins/adapters/python_plugin.py` | Use shared `_safe_extract_zip()` from loader |
| `backend/app/gateway/router.py` | Add deprecation docstring noting test-only status |
| `backend/tests/infra/test_redis.py` | DELETE |
| `backend/tests/infra/test_ollama_discovery.py` | Update import path |

### Existing test files to verify still pass (no modifications expected)
- `backend/tests/api/test_cron.py`
- `backend/tests/api/test_workspaces.py`
- `backend/tests/api/test_documents.py`
- `backend/tests/gateway/test_gateway.py`
- `backend/tests/gateway/test_security.py`

---

### Task 1: Remove Middle-Man Wrappers (🟢 Suggestion fix)

**Files:**
- Delete: `backend/app/infra/redis.py`
- Delete: `backend/tests/infra/test_redis.py`
- Delete: `backend/app/infra/ollama.py`
- Modify: `backend/tests/infra/test_ollama_discovery.py`
- Modify: `backend/app/main.py:69-82`

- [ ] **Step 1: Verify no production code imports `get_redis_url`**

Run: `cd /Users/hyh/code/JARVIS/backend && grep -r "get_redis_url\|from app.infra.redis" app/ --include="*.py"`
Expected: No matches (only tests import it).

- [ ] **Step 2: Delete `infra/redis.py` and its test**

Delete `backend/app/infra/redis.py` and `backend/tests/infra/test_redis.py`.

- [ ] **Step 3: Update ollama test to import from canonical location**

Change `backend/tests/infra/test_ollama_discovery.py` line 5:

```python
# Before:
from app.infra.ollama import get_ollama_models
# After:
from app.services.model_discovery import get_ollama_models
```

- [ ] **Step 4: Delete `infra/ollama.py`**

Delete `backend/app/infra/ollama.py`.

- [ ] **Step 5: Replace `_ConcreteGraphFactory` with simple function in main.py**

In `backend/app/main.py`, replace lines 69-82:

```python
# Before:
class _ConcreteGraphFactory:
    """Thin wrapper — delegates to ``create_graph`` with kwargs from subagent_tool."""

    async def create(
        self,
        messages: object,
        config: object,
    ) -> object:
        from app.agent.graph import create_graph

        return create_graph(**(config if isinstance(config, dict) else {}))


_set_subagent_graph_factory(_ConcreteGraphFactory())  # type: ignore[arg-type]

# After:
class _ConcreteGraphFactory:
    """Satisfies the ``AgentGraphFactory`` protocol for subagent_tool."""

    async def create(self, messages: object, config: object) -> object:
        from app.agent.graph import create_graph

        return create_graph(**(config if isinstance(config, dict) else {}))


_set_subagent_graph_factory(_ConcreteGraphFactory())  # type: ignore[arg-type]
```

NOTE: Keep the class — it must satisfy the `AgentGraphFactory` Protocol (which requires an `async def create(self, ...)` method). A plain function cannot satisfy a Protocol with a method signature. Just compress to a clean 2-line body.

- [ ] **Step 6: Run tests**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/infra/ tests/tools/test_subagent_tool.py -v --tb=short`
Expected: All tests pass. `test_redis.py` is gone, `test_ollama_discovery.py` passes with new import.

- [ ] **Step 7: Commit**

```bash
git add -A backend/app/infra/redis.py backend/app/infra/ollama.py backend/tests/infra/
git commit -m "refactor: remove middle-man wrappers (redis.py, ollama.py)"
```

---

### Task 2: Centralized Authorization Service (🔴 Critical fix — part 1)

**Files:**
- Create: `backend/app/services/authorization.py`
- Create: `backend/tests/services/test_authorization.py`

- [ ] **Step 1: Write failing tests for authorization helpers**

Create `backend/tests/services/test_authorization.py`:

```python
"""Tests for centralized authorization helpers."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.authorization import (
    assert_doc_write_access,
    require_org,
    require_workspace_role,
)


@pytest.mark.anyio
async def test_require_org_raises_when_no_org_id():
    user = MagicMock()
    user.organization_id = None
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await require_org(user, db)
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_require_org_raises_when_org_not_found():
    user = MagicMock()
    user.organization_id = uuid.uuid4()
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc_info:
        await require_org(user, db)
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_require_org_returns_org():
    user = MagicMock()
    user.organization_id = uuid.uuid4()
    org = MagicMock()
    db = AsyncMock()
    db.get = AsyncMock(return_value=org)
    result = await require_org(user, db)
    assert result is org


@pytest.mark.anyio
async def test_require_workspace_role_denies_non_member():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_role(
            workspace_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            db=db,
            allowed_roles=frozenset({"owner", "admin"}),
        )
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_require_workspace_role_denies_wrong_role():
    membership = MagicMock()
    membership.role = "member"
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=membership)
    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_role(
            workspace_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            db=db,
            allowed_roles=frozenset({"owner", "admin"}),
        )
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_require_workspace_role_allows_valid_role():
    membership = MagicMock()
    membership.role = "admin"
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=membership)
    result = await require_workspace_role(
        workspace_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        db=db,
        allowed_roles=frozenset({"owner", "admin"}),
    )
    assert result is membership


@pytest.mark.anyio
async def test_assert_doc_write_access_personal_doc_owner_allowed():
    doc = MagicMock()
    doc.workspace_id = None
    user = MagicMock()
    user.id = uuid.uuid4()
    doc.user_id = user.id
    db = AsyncMock()
    # Should not raise
    await assert_doc_write_access(doc, user, db)


@pytest.mark.anyio
async def test_assert_doc_write_access_personal_doc_non_owner_denied():
    doc = MagicMock()
    doc.workspace_id = None
    doc.user_id = uuid.uuid4()
    user = MagicMock()
    user.id = uuid.uuid4()
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await assert_doc_write_access(doc, user, db)
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_assert_doc_write_access_workspace_doc_admin_allowed():
    doc = MagicMock()
    doc.workspace_id = uuid.uuid4()
    user = MagicMock()
    user.id = uuid.uuid4()
    membership = MagicMock()
    membership.role = "admin"
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=membership)
    # Should not raise
    await assert_doc_write_access(doc, user, db)


@pytest.mark.anyio
async def test_assert_doc_write_access_workspace_doc_member_denied():
    doc = MagicMock()
    doc.workspace_id = uuid.uuid4()
    user = MagicMock()
    user.id = uuid.uuid4()
    membership = MagicMock()
    membership.role = "member"
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=membership)
    with pytest.raises(HTTPException) as exc_info:
        await assert_doc_write_access(doc, user, db)
    assert exc_info.value.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/services/test_authorization.py -v --tb=short`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.authorization'`

- [ ] **Step 3: Implement authorization service**

Create `backend/app/services/authorization.py`:

```python
"""Centralized authorization helpers.

Consolidates access-control checks previously scattered across API routes
(documents.py, workspaces.py, etc.) into reusable functions.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import Organization, WorkspaceMember

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import Document, User

_PRIVILEGED_ROLES = frozenset({"owner", "admin"})


async def require_org(user: User, db: AsyncSession) -> Organization:
    """Return the user's organization or raise 403."""
    if not user.organization_id:
        raise HTTPException(
            status_code=403, detail="You must belong to an organization"
        )
    org = await db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(status_code=403, detail="Organization not found")
    return org


async def require_workspace_role(
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    allowed_roles: frozenset[str] = _PRIVILEGED_ROLES,
) -> WorkspaceMember:
    """Return membership if user has an allowed role, otherwise raise 403."""
    membership = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if not membership or membership.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Not authorized")
    return membership


async def assert_doc_write_access(
    doc: Document,
    user: User,
    db: AsyncSession,
) -> None:
    """Raise HTTPException if user lacks write permission on a document.

    Workspace documents: allow owner/admin members.
    Personal documents: allow only the original uploader.
    """
    if doc.workspace_id is not None:
        await require_workspace_role(
            workspace_id=doc.workspace_id,
            user_id=user.id,
            db=db,
        )
    elif doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document not found")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/services/test_authorization.py -v --tb=short`
Expected: All 10 tests pass.

- [ ] **Step 5: Wire authorization into API routes**

**In `backend/app/api/documents.py`**, replace the local `_assert_doc_write_access` with the centralized version:

```python
# Remove the local function _assert_doc_write_access (lines 62-82)
# Remove local _PRIVILEGED_ROLES (line 42)
# Add import at top:
from app.services.authorization import assert_doc_write_access
```

Then update all call sites from `_assert_doc_write_access(...)` to `assert_doc_write_access(...)` (should be zero signature change — same args).

**In `backend/app/api/workspaces.py`**, replace the local `_require_org` with the centralized version:

```python
# Remove the local function _require_org (lines 48-57)
# Remove local _PRIVILEGED_ROLES (line 26)
# Add import at top:
from app.services.authorization import require_org, require_workspace_role
```

Then update all call sites:
- `_require_org(user, db)` → `require_org(user, db)`
- Inline role checks (e.g., lines 112-122 in update_workspace) → `await require_workspace_role(workspace_id=ws_id, user_id=user.id, db=db)`

- [ ] **Step 6: Rename `_get_qdrant_collection` → `get_document_collection` (🟢 Naming fix)**

In `backend/app/api/documents.py`, rename the function:

```python
# Before:
async def _get_qdrant_collection(
    workspace_id: uuid.UUID | None,
    user: User,
    db: AsyncSession,
) -> str:
    """Get the Qdrant collection name for a user or workspace document."""

# After:
async def get_document_collection(
    workspace_id: uuid.UUID | None,
    user: User,
    db: AsyncSession,
) -> str:
    """Return the vector collection name for a user or workspace.

    For workspace documents: validates membership and returns workspace collection.
    For personal documents: returns user collection.
    """
```

Update all call sites in the same file (should be 2-3 occurrences).

- [ ] **Step 7: Run full API test suite**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/api/test_documents.py tests/api/test_workspaces.py tests/services/test_authorization.py -v --tb=short`
Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/authorization.py backend/tests/services/test_authorization.py backend/app/api/documents.py backend/app/api/workspaces.py
git commit -m "refactor: centralize authorization into services/authorization.py"
```

---

### Task 3: CronJob Domain Model Enrichment (🔴 Critical fix — part 2)

**Files:**
- Modify: `backend/app/db/models/scheduler.py`
- Create: `backend/tests/db/test_cron_job_model.py`

- [ ] **Step 1: Write failing tests for CronJob domain methods**

Create `backend/tests/db/test_cron_job_model.py`:

```python
"""Tests for CronJob domain model methods."""

import uuid

import pytest

from app.db.models.scheduler import CronJob


def test_create_factory():
    job = CronJob.create(
        user_id=uuid.uuid4(),
        schedule="0 * * * *",
        task="check website",
        trigger_type="cron",
    )
    assert job.id is not None
    assert job.schedule == "0 * * * *"
    assert job.task == "check website"
    assert job.trigger_type == "cron"
    assert job.is_active is True


def test_create_factory_with_workspace():
    ws_id = uuid.uuid4()
    job = CronJob.create(
        user_id=uuid.uuid4(),
        schedule="*/5 * * * *",
        task="monitor",
        trigger_type="web_watcher",
        workspace_id=ws_id,
        trigger_metadata={"url": "https://example.com"},
    )
    assert job.workspace_id == ws_id
    assert job.trigger_metadata == {"url": "https://example.com"}


def test_validate_trigger_type_valid():
    # Should not raise
    CronJob.validate_trigger_type("cron")
    CronJob.validate_trigger_type("web_watcher")
    CronJob.validate_trigger_type("semantic_watcher")
    CronJob.validate_trigger_type("email")


def test_validate_trigger_type_invalid():
    with pytest.raises(ValueError, match="Invalid trigger_type"):
        CronJob.validate_trigger_type("invalid_type")


def test_toggle_active():
    job = CronJob.create(
        user_id=uuid.uuid4(),
        schedule="0 * * * *",
        task="test",
        trigger_type="cron",
    )
    assert job.is_active is True
    job.toggle()
    assert job.is_active is False
    job.toggle()
    assert job.is_active is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/db/test_cron_job_model.py -v --tb=short`
Expected: FAIL — `AttributeError: type object 'CronJob' has no attribute 'create'`

- [ ] **Step 3: Add domain methods to CronJob**

In `backend/app/db/models/scheduler.py`, add to the `CronJob` class after the column definitions:

```python
    _VALID_TRIGGER_TYPES = frozenset({"cron", "web_watcher", "semantic_watcher", "email"})

    @classmethod
    def create(
        cls,
        *,
        user_id: uuid.UUID,
        schedule: str,
        task: str,
        trigger_type: str,
        workspace_id: uuid.UUID | None = None,
        trigger_metadata: dict | None = None,
    ) -> "CronJob":
        """Factory method — validates trigger_type before construction."""
        cls.validate_trigger_type(trigger_type)
        return cls(
            id=uuid.uuid4(),
            user_id=user_id,
            schedule=schedule,
            task=task,
            trigger_type=trigger_type,
            workspace_id=workspace_id,
            trigger_metadata=trigger_metadata,
        )

    @classmethod
    def validate_trigger_type(cls, trigger_type: str) -> None:
        """Raise ValueError if trigger_type is not recognized."""
        if trigger_type not in cls._VALID_TRIGGER_TYPES:
            valid = sorted(cls._VALID_TRIGGER_TYPES)
            raise ValueError(f"Invalid trigger_type '{trigger_type}'. Must be one of: {valid}")

    def toggle(self) -> None:
        """Flip the is_active flag."""
        self.is_active = not self.is_active
```

Add `import uuid` at the top if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/db/test_cron_job_model.py -v --tb=short`
Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models/scheduler.py backend/tests/db/test_cron_job_model.py
git commit -m "feat: add CronJob.create(), validate_trigger_type(), toggle() domain methods"
```

---

### Task 4: CronService — Extract Business Logic from API (🔴 Critical fix — part 3)

**Files:**
- Create: `backend/app/services/cron_service.py`
- Create: `backend/tests/services/test_cron_service.py`
- Modify: `backend/app/api/cron.py`

- [ ] **Step 1: Write failing tests for CronService**

Create `backend/tests/services/test_cron_service.py`:

```python
"""Tests for CronService business logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.cron_service import CronService


def _make_service(db=None):
    if db is None:
        db = AsyncMock()
    return CronService(db)


@pytest.mark.anyio
async def test_check_quota_under_limit():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=3)
    svc = _make_service(db)
    # Should not raise with default limit (assumed > 3)
    with patch("app.services.cron_service.settings") as mock_settings:
        mock_settings.max_cron_jobs_per_user = 10
        await svc.check_quota(uuid.uuid4())


@pytest.mark.anyio
async def test_check_quota_at_limit_raises():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=10)
    svc = _make_service(db)
    with patch("app.services.cron_service.settings") as mock_settings:
        mock_settings.max_cron_jobs_per_user = 10
        with pytest.raises(HTTPException) as exc_info:
            await svc.check_quota(uuid.uuid4())
        assert exc_info.value.status_code == 429


@pytest.mark.anyio
async def test_encrypt_email_metadata():
    svc = _make_service()
    metadata = {"imap_server": "imap.gmail.com", "imap_password": "secret123"}
    with patch("app.services.cron_service.fernet_encrypt", return_value="encrypted"):
        result = svc.prepare_trigger_metadata("email", metadata)
    assert result["imap_password"] == "encrypted"
    assert result["imap_server"] == "imap.gmail.com"


@pytest.mark.anyio
async def test_prepare_metadata_non_email_unchanged():
    svc = _make_service()
    metadata = {"url": "https://example.com"}
    result = svc.prepare_trigger_metadata("web_watcher", metadata)
    assert result == {"url": "https://example.com"}


@pytest.mark.anyio
async def test_prepare_metadata_none_returns_none():
    svc = _make_service()
    result = svc.prepare_trigger_metadata("cron", None)
    assert result is None


@pytest.mark.anyio
async def test_create_job_calls_validate_and_quota():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=0)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    svc = _make_service(db)

    with (
        patch("app.services.cron_service.settings") as mock_settings,
        patch("app.services.cron_service.validate_trigger_metadata"),
        patch("app.services.cron_service.register_cron_job", return_value=None),
    ):
        mock_settings.max_cron_jobs_per_user = 10
        job = await svc.create_job(
            user_id=uuid.uuid4(),
            schedule="0 * * * *",
            task="test",
            trigger_type="cron",
        )
    assert job is not None
    db.add.assert_called_once()
    db.commit.assert_awaited()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/services/test_cron_service.py -v --tb=short`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.cron_service'`

- [ ] **Step 3: Implement CronService**

Create `backend/app/services/cron_service.py`:

```python
"""CronJob business logic — extracted from api/cron.py.

Owns: validation, quota enforcement, metadata encryption, scheduler registration.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import HTTPException
from sqlalchemy import func as sql_func
from sqlalchemy import select

from app.core.config import settings
from app.core.security import fernet_encrypt
from app.db.models import CronJob
from app.scheduler.runner import register_cron_job, unregister_cron_job
from app.scheduler.trigger_schemas import validate_trigger_metadata

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class CronService:
    """Domain service for CronJob lifecycle operations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def check_quota(self, user_id: uuid.UUID) -> None:
        """Raise 429 if the user has reached the active job limit."""
        active_count = await self._db.scalar(
            select(sql_func.count()).where(
                CronJob.user_id == user_id,
                CronJob.is_active.is_(True),
            )
        )
        if (active_count or 0) >= settings.max_cron_jobs_per_user:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Job quota exceeded "
                    f"(max {settings.max_cron_jobs_per_user} active jobs)"
                ),
            )

    def prepare_trigger_metadata(
        self,
        trigger_type: str,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Encrypt sensitive fields in trigger metadata (e.g. email passwords)."""
        if metadata is None:
            return None
        result = dict(metadata)
        if trigger_type == "email" and "imap_password" in result:
            result["imap_password"] = fernet_encrypt(str(result["imap_password"]))
        return result

    async def create_job(
        self,
        *,
        user_id: uuid.UUID,
        schedule: str,
        task: str,
        trigger_type: str,
        trigger_metadata: dict[str, Any] | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> CronJob:
        """Validate, enforce quota, persist, and register a new CronJob."""
        CronJob.validate_trigger_type(trigger_type)

        try:
            validate_trigger_metadata(trigger_type, trigger_metadata or {})
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid trigger_metadata: {exc}",
            ) from exc

        await self.check_quota(user_id)

        prepared_metadata = self.prepare_trigger_metadata(
            trigger_type, trigger_metadata
        )

        job = CronJob.create(
            user_id=user_id,
            schedule=schedule,
            task=task,
            trigger_type=trigger_type,
            workspace_id=workspace_id,
            trigger_metadata=prepared_metadata,
        )
        self._db.add(job)
        await self._db.commit()
        await self._db.refresh(job)

        if job.is_active:
            next_run_time = register_cron_job(str(job.id), job.schedule)
            if next_run_time:
                job.next_run_at = next_run_time
                await self._db.commit()

        return job

    async def update_job(
        self,
        job: CronJob,
        *,
        schedule: str | None = None,
        task: str | None = None,
        trigger_metadata: dict[str, Any] | None = None,
    ) -> CronJob:
        """Update mutable fields on an existing job, re-register if active."""
        if trigger_metadata is not None:
            try:
                validate_trigger_metadata(job.trigger_type, trigger_metadata)
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid trigger_metadata: {exc}",
                ) from exc

        if schedule is not None:
            job.schedule = schedule
        if task is not None:
            job.task = task
        if trigger_metadata is not None:
            job.trigger_metadata = self.prepare_trigger_metadata(
                job.trigger_type, trigger_metadata
            )
        await self._db.commit()

        if job.is_active:
            unregister_cron_job(str(job.id))
            next_run_time = register_cron_job(str(job.id), job.schedule)
            if next_run_time:
                job.next_run_at = next_run_time
                await self._db.commit()

        return job

    async def delete_job(self, job: CronJob) -> None:
        """Unregister and delete a job."""
        unregister_cron_job(str(job.id))
        await self._db.delete(job)
        await self._db.commit()

    async def toggle_job(self, job: CronJob) -> CronJob:
        """Toggle active/inactive and update scheduler registration."""
        job.toggle()
        await self._db.commit()

        if job.is_active:
            next_run_time = register_cron_job(str(job.id), job.schedule)
            if next_run_time:
                job.next_run_at = next_run_time
                await self._db.commit()
        else:
            unregister_cron_job(str(job.id))
            job.next_run_at = None
            await self._db.commit()

        return job
```

- [ ] **Step 4: Run service tests**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/services/test_cron_service.py -v --tb=short`
Expected: All 6 tests pass.

- [ ] **Step 5: Thin down `api/cron.py` to use CronService**

Replace the business logic in `backend/app/api/cron.py`:

1. Add import: `from app.services.cron_service import CronService`
2. Remove: `_VALID_TRIGGER_TYPES` set (line 29) — now lives in `CronJob._VALID_TRIGGER_TYPES`
3. Remove: inline trigger_type validation, quota check, metadata encryption from `create_cron_job()` (lines 131-171)
4. Replace with service call:

```python
@router.post("")
@limiter.limit("10/minute")
async def create_cron_job(
    request: Request,
    data: CronJobCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Create a new proactive monitoring job."""
    if data.workspace_id is not None:
        await require_workspace_member(data.workspace_id, user, db)

    svc = CronService(db)
    job = await svc.create_job(
        user_id=user.id,
        schedule=data.schedule,
        task=data.task,
        trigger_type=data.trigger_type,
        trigger_metadata=data.trigger_metadata,
        workspace_id=data.workspace_id,
    )
    return {"status": "ok", "id": str(job.id)}
```

5. Similarly thin down `update_cron_job()`:

```python
@router.put("/{job_id}")
@limiter.limit("20/minute")
async def update_cron_job(
    request: Request,
    job_id: uuid.UUID,
    data: CronJobUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update schedule, task, or trigger_metadata of an existing job."""
    job = await db.get(CronJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    svc = CronService(db)
    await svc.update_job(
        job,
        schedule=data.schedule,
        task=data.task,
        trigger_metadata=data.trigger_metadata,
    )
    return {"status": "ok", "id": str(job.id)}
```

6. Similarly thin down `delete_cron_job()` and `toggle_cron_job()`:

```python
@router.delete("/{job_id}", status_code=204)
@limiter.limit("30/minute")
async def delete_cron_job(
    request: Request,
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a monitoring job."""
    job = await db.get(CronJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    svc = CronService(db)
    await svc.delete_job(job)


@router.patch("/{job_id}/toggle")
@limiter.limit("30/minute")
async def toggle_cron_job(
    request: Request,
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Enable or disable a monitoring job."""
    job = await db.get(CronJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    svc = CronService(db)
    await svc.toggle_job(job)
    return {"status": "ok", "is_active": job.is_active}
```

7. Remove unused imports that were only needed for the inlined business logic: `fernet_encrypt`, `validate_trigger_metadata`, `sql_func`, `settings` (if no longer used).

- [ ] **Step 6: Run full cron test suite**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/api/test_cron.py tests/services/test_cron_service.py tests/db/test_cron_job_model.py -v --tb=short`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/cron_service.py backend/tests/services/test_cron_service.py backend/app/api/cron.py
git commit -m "refactor: extract CronService from api/cron.py routes"
```

---

### Task 5: Workspace Domain Model + Service (🔴 Critical fix — part 4)

**Files:**
- Modify: `backend/app/db/models/organization.py`
- Create: `backend/app/services/workspace_service.py`
- Create: `backend/tests/services/test_workspace_service.py`
- Create: `backend/tests/db/test_workspace_model.py`
- Modify: `backend/app/api/workspaces.py`

- [ ] **Step 1: Write failing tests for Workspace domain methods**

Create `backend/tests/db/test_workspace_model.py`:

```python
"""Tests for Workspace and WorkspaceMember domain methods."""

import uuid

from app.db.models.organization import Workspace, WorkspaceMember


def test_workspace_soft_delete():
    ws = Workspace(id=uuid.uuid4(), name="Test", organization_id=uuid.uuid4())
    assert ws.is_deleted is False
    ws.soft_delete()
    assert ws.is_deleted is True


def test_workspace_member_is_privileged_owner():
    m = WorkspaceMember(
        workspace_id=uuid.uuid4(), user_id=uuid.uuid4(), role="owner"
    )
    assert m.is_privileged() is True


def test_workspace_member_is_privileged_admin():
    m = WorkspaceMember(
        workspace_id=uuid.uuid4(), user_id=uuid.uuid4(), role="admin"
    )
    assert m.is_privileged() is True


def test_workspace_member_is_privileged_member():
    m = WorkspaceMember(
        workspace_id=uuid.uuid4(), user_id=uuid.uuid4(), role="member"
    )
    assert m.is_privileged() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/db/test_workspace_model.py -v --tb=short`
Expected: FAIL — `AttributeError: 'Workspace' object has no attribute 'soft_delete'`

- [ ] **Step 3: Add domain methods to models**

In `backend/app/db/models/organization.py`, add to `Workspace` class:

```python
    def soft_delete(self) -> None:
        """Mark workspace as deleted."""
        self.is_deleted = True
```

Add to `WorkspaceMember` class:

```python
    _PRIVILEGED_ROLES = frozenset({"owner", "admin"})

    def is_privileged(self) -> bool:
        """Return True if this member has owner or admin role."""
        return self.role in self._PRIVILEGED_ROLES
```

- [ ] **Step 4: Run model tests**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/db/test_workspace_model.py -v --tb=short`
Expected: All 4 tests pass.

- [ ] **Step 5: Write failing tests for WorkspaceService**

Create `backend/tests/services/test_workspace_service.py`:

```python
"""Tests for WorkspaceService business logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.workspace_service import WorkspaceService


def _make_service(db=None):
    if db is None:
        db = AsyncMock()
    return WorkspaceService(db)


@pytest.mark.anyio
async def test_create_workspace():
    org = MagicMock()
    org.id = uuid.uuid4()
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    svc = _make_service(db)
    with patch(
        "app.services.workspace_service.require_org", new=AsyncMock(return_value=org)
    ):
        ws = await svc.create_workspace(user=MagicMock(), name="Test WS")
    assert ws.name == "Test WS"
    assert ws.organization_id == org.id
    db.add.assert_called_once()


@pytest.mark.anyio
async def test_update_workspace_not_found():
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    svc = _make_service(db)
    with pytest.raises(HTTPException) as exc_info:
        await svc.update_workspace(
            ws_id=uuid.uuid4(),
            user=MagicMock(organization_id=uuid.uuid4()),
            name="New Name",
        )
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_update_workspace_wrong_org():
    ws = MagicMock()
    ws.is_deleted = False
    ws.organization_id = uuid.uuid4()
    user = MagicMock()
    user.organization_id = uuid.uuid4()  # Different org
    user.id = uuid.uuid4()
    db = AsyncMock()
    db.get = AsyncMock(return_value=ws)
    svc = _make_service(db)
    with pytest.raises(HTTPException) as exc_info:
        await svc.update_workspace(ws_id=uuid.uuid4(), user=user, name="New")
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_delete_workspace_non_owner():
    ws = MagicMock()
    ws.is_deleted = False
    ws.organization_id = uuid.uuid4()
    org = MagicMock()
    org.id = ws.organization_id
    org.owner_id = uuid.uuid4()  # Different owner
    user = MagicMock()
    user.id = uuid.uuid4()
    user.organization_id = org.id
    db = AsyncMock()
    db.get = AsyncMock(return_value=ws)

    svc = _make_service(db)
    with patch(
        "app.services.workspace_service.require_org", new=AsyncMock(return_value=org)
    ):
        with pytest.raises(HTTPException) as exc_info:
            await svc.delete_workspace(ws_id=uuid.uuid4(), user=user)
    assert exc_info.value.status_code == 403
```

- [ ] **Step 6: Implement WorkspaceService**

Create `backend/app/services/workspace_service.py`:

```python
"""Workspace business logic — extracted from api/workspaces.py."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from fastapi import HTTPException

from app.db.models import Workspace
from app.services.authorization import require_org, require_workspace_role

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import User

logger = structlog.get_logger(__name__)


class WorkspaceService:
    """Domain service for Workspace lifecycle operations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_workspace(self, *, user: User, name: str) -> Workspace:
        """Create a new workspace in the user's organization."""
        org = await require_org(user, self._db)
        ws = Workspace(name=name, organization_id=org.id)
        self._db.add(ws)
        await self._db.commit()
        await self._db.refresh(ws)
        logger.info("workspace_created", ws_id=str(ws.id), org_id=str(org.id))
        return ws

    async def update_workspace(
        self,
        *,
        ws_id: uuid.UUID,
        user: User,
        name: str,
    ) -> Workspace:
        """Update workspace name. Requires owner/admin role."""
        ws = await self._db.get(Workspace, ws_id)
        if not ws or ws.is_deleted:
            raise HTTPException(status_code=404, detail="Workspace not found")
        if ws.organization_id != user.organization_id:
            raise HTTPException(status_code=403, detail="Access denied")
        await require_workspace_role(
            workspace_id=ws_id, user_id=user.id, db=self._db
        )
        ws.name = name
        await self._db.commit()
        return ws

    async def delete_workspace(
        self,
        *,
        ws_id: uuid.UUID,
        user: User,
    ) -> None:
        """Soft-delete a workspace. Only the org owner may do this."""
        org = await require_org(user, self._db)
        ws = await self._db.get(Workspace, ws_id)
        if not ws or ws.is_deleted:
            raise HTTPException(status_code=404, detail="Workspace not found")
        if ws.organization_id != org.id:
            raise HTTPException(status_code=403, detail="Access denied")
        if org.owner_id != user.id:
            raise HTTPException(
                status_code=403, detail="Only the owner can delete workspaces"
            )
        ws.soft_delete()
        await self._db.commit()
```

- [ ] **Step 7: Run service tests**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/services/test_workspace_service.py tests/db/test_workspace_model.py -v --tb=short`
Expected: All tests pass.

- [ ] **Step 8: Thin down `api/workspaces.py`**

Update `backend/app/api/workspaces.py`:

1. Add imports: `from app.services.workspace_service import WorkspaceService`
2. Remove: local `_require_org`, `_PRIVILEGED_ROLES`
3. Replace `create_workspace`, `update_workspace`, `delete_workspace` bodies with service calls:

```python
@router.post("", status_code=201)
@limiter.limit("60/minute")
async def create_workspace(
    request: Request,
    body: WorkspaceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new workspace in the user's organization."""
    svc = WorkspaceService(db)
    ws = await svc.create_workspace(user=user, name=body.name)
    return _ws_to_dict(ws)


@router.put("/{ws_id}")
@limiter.limit("60/minute")
async def update_workspace(
    request: Request,
    ws_id: uuid.UUID,
    body: WorkspaceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update workspace name. User must be an owner or admin."""
    svc = WorkspaceService(db)
    ws = await svc.update_workspace(ws_id=ws_id, user=user, name=body.name)
    return _ws_to_dict(ws)


@router.delete("/{ws_id}", status_code=204)
@limiter.limit("60/minute")
async def delete_workspace(
    request: Request,
    ws_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a workspace. Only org owner may do this."""
    svc = WorkspaceService(db)
    await svc.delete_workspace(ws_id=ws_id, user=user)
```

4. Keep `list_workspaces`, `list_members`, settings endpoints unchanged (they are thin queries, not business logic).
5. For settings endpoints, replace inline role checks with `require_workspace_role` from authorization module where applicable.

- [ ] **Step 9: Run full workspace test suite**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/api/test_workspaces.py tests/services/test_workspace_service.py tests/db/test_workspace_model.py -v --tb=short`
Expected: All tests pass.

- [ ] **Step 10: Commit**

```bash
git add backend/app/db/models/organization.py backend/app/services/workspace_service.py backend/tests/services/test_workspace_service.py backend/tests/db/test_workspace_model.py backend/app/api/workspaces.py
git commit -m "refactor: extract WorkspaceService + domain model methods"
```

---

### Task 6: Annotate GatewayRouter as Test-Only (🟡 Warning fix)

**Files:**
- Modify: `backend/app/gateway/router.py`

- [ ] **Step 1: Add deprecation/status annotation to GatewayRouter**

In `backend/app/gateway/router.py`, update the class docstring:

```python
class GatewayRouter:
    """Routes incoming messages from any channel to the appropriate agent session.

    .. warning:: **Not wired into production.**
       This class is fully implemented and tested but no production code path
       instantiates it.  Channel adapters' ``_message_handler`` callbacks are
       never set outside of tests.  If channel-based message handling is not
       on the roadmap, consider removing this module to reduce maintenance cost.

    The router is intentionally kept thin: it resolves the session, delegates
    to a pluggable agent callable, and returns the reply string.  The actual
    LangGraph invocation lives outside this class so it can be replaced in
```

- [ ] **Step 2: Run gateway tests to verify nothing broke**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/gateway/ -v --tb=short`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/app/gateway/router.py
git commit -m "docs: annotate GatewayRouter as test-only, not wired in production"
```

---

### Task 7: Consolidate Plugin ZIP Extraction (🟢 Suggestion fix)

**Files:**
- Modify: `backend/app/plugins/loader.py`
- Modify: `backend/app/plugins/adapters/python_plugin.py`

- [ ] **Step 1: Extract shared `safe_extract_zip` helper into loader.py**

In `backend/app/plugins/loader.py`, add a shared helper (before `install_plugin_from_url`):

```python
def safe_extract_zip(data: bytes, dest: Path) -> None:
    """Extract a ZIP archive to *dest*, filtering out unsafe path entries.

    Rejects entries with absolute paths or ``..`` components to prevent
    zip-slip attacks.  Runs synchronously — callers should wrap with
    ``asyncio.to_thread`` if needed.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        safe_members = [
            m
            for m in z.infolist()
            if not (
                m.filename.startswith("/")
                or ".." in m.filename.replace("\\", "/").split("/")
            )
        ]
        z.extractall(dest, members=safe_members)
```

Then update `install_plugin_from_url` to use it:

```python
        # Handle .zip (OpenClaw skill package)
        if url.endswith(".zip") or "archive" in url:
            # ... (keep pkg_name computation)
            extract_path = _DEFAULT_PLUGIN_DIR / pkg_name
            safe_extract_zip(response.content, extract_path)
            # ... (keep nested dir handling)
```

- [ ] **Step 2: Update `python_plugin.py` to use shared helper**

In `backend/app/plugins/adapters/python_plugin.py`:

```python
# Add import:
from app.plugins.loader import safe_extract_zip

# Replace the local _extract function (lines 51-61) with:
        await asyncio.to_thread(safe_extract_zip, response.content, pkg_dir)
```

Remove the local `_extract` function definition.

- [ ] **Step 3: Run plugin tests**

Run: `cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/ -k "plugin" -v --tb=short`
Expected: All plugin tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/plugins/loader.py backend/app/plugins/adapters/python_plugin.py
git commit -m "refactor: consolidate ZIP extraction into shared safe_extract_zip()"
```

---

### Task 8: Final Verification

- [ ] **Step 1: Run full static checks**

```bash
cd /Users/hyh/code/JARVIS/backend && uv run ruff check --fix && uv run ruff format
cd /Users/hyh/code/JARVIS/backend && uv run mypy app
```

- [ ] **Step 2: Run import collection check**

```bash
cd /Users/hyh/code/JARVIS/backend && uv run pytest --collect-only -q
```
Expected: No import errors.

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/hyh/code/JARVIS/backend && uv run pytest tests/ -v --tb=short
```
Expected: All 900+ tests pass.

- [ ] **Step 4: Squash-friendly commit summary**

If all tests pass, the branch is ready for the quality loop (simplify + review).
