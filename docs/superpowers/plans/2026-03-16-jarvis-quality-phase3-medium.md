# JARVIS Quality — Phase 3: Medium-Priority Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 11 Medium-severity issues covering error recovery, data integrity, validation, performance, and UX.

**Architecture:** Each task is a self-contained PR. TDD: failing test first, then fix.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Alembic, Vue 3 + TypeScript, Pydantic v2

**Spec:** `docs/superpowers/specs/2026-03-16-jarvis-quality-perfection-design.md`

**Prerequisite:** Phase 1 and Phase 2 complete.

---

## Chunk 1: PR-13 — Exception Handling Without Recovery Logic

**Branch:** `fix/medium-core-exception-no-recovery`

### Task 1: Write failing test

**Files:**
- Test: `backend/tests/test_retry_decorator.py` (new)

- [ ] **Step 1: Write test for retry behavior**

```python
# backend/tests/test_retry_decorator.py
"""Test: retry_async decorator retries on transient errors with backoff."""
import asyncio
import pytest


@pytest.mark.anyio
async def test_retry_async_retries_on_transient_error():
    """retry_async must retry up to max_attempts times on specified exceptions.

    FAILS before fix: retry_async does not exist.
    PASSES after fix: decorator retries and succeeds on final attempt.
    """
    try:
        from app.core.retry import retry_async
    except ImportError:
        pytest.fail("retry_async not found in app.core.retry")

    call_count = 0

    @retry_async(max_attempts=3, base_delay=0.0, exceptions=(OSError,))
    async def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise OSError("transient error")
        return "ok"

    result = await flaky_func()
    assert result == "ok"
    assert call_count == 3, f"Expected 3 attempts, got {call_count}"


@pytest.mark.anyio
async def test_retry_async_raises_after_max_attempts():
    """retry_async must re-raise after exhausting all attempts.

    FAILS before fix: retry_async does not exist.
    PASSES after fix: raises OSError after max_attempts.
    """
    from app.core.retry import retry_async

    call_count = 0

    @retry_async(max_attempts=2, base_delay=0.0, exceptions=(OSError,))
    async def always_fails():
        nonlocal call_count
        call_count += 1
        raise OSError("permanent error")

    with pytest.raises(OSError, match="permanent error"):
        await always_fails()
    assert call_count == 2
```

- [ ] **Step 2: Run — FAIL (retry_async doesn't exist yet)**

```bash
cd backend && uv run pytest tests/test_retry_decorator.py -v
```

---

### Task 2: Add retry utility

**Files:**
- Create: `backend/app/core/retry.py`

- [ ] **Step 1: Add retry decorator**

```python
# backend/app/core/retry.py
"""Retry utilities for transient I/O errors."""
from functools import wraps
from typing import Callable, Type
import asyncio
import structlog

logger = structlog.get_logger(__name__)


def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple[Type[Exception], ...] = (OSError,),
) -> Callable:
    """Exponential backoff retry decorator for async functions.

    Args:
        max_attempts: Maximum number of attempts (including the first).
        base_delay: Base delay in seconds; actual delay = base_delay * 2 ** attempt.
        exceptions: Exception types to retry on.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts - 1:
                        raise
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "retrying_after_transient_error",
                        func=func.__name__,
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)
        return wrapper
    return decorator
```

- [ ] **Step 2: Apply to channel send functions (grep for bare except in channels)**

```bash
cd backend && grep -rn "except Exception" app/channels/ --include="*.py" -l
```

For each channel file, wrap its main `send` method with `@retry_async(max_attempts=3, base_delay=0.5, exceptions=(OSError, ConnectionError))`.

- [ ] **Step 3: Run test**

```bash
cd backend && uv run pytest tests/test_retry_decorator.py -v
```

- [ ] **Step 4: Static checks + commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
git checkout -b fix/medium-core-exception-no-recovery dev
git add backend/app/core/retry.py backend/app/channels/ backend/tests/test_retry_decorator.py
git commit -m "fix(core): add retry_async decorator with exponential backoff for transient I/O errors"
```

---

## Chunk 2: PR-14 — Organization Cascade Delete Missing

**Branch:** `fix/medium-db-org-cascade-delete`

### Task 3: Write failing test

**Files:**
- Test: `backend/tests/db/test_org_cascade_delete.py` (new)

- [ ] **Step 1: Write test**

```python
# backend/tests/db/test_org_cascade_delete.py
"""Test: deleting an Organization must cascade to Workspaces."""
import uuid
import pytest
from sqlalchemy import select
from app.db.models import Organization, Workspace, User


@pytest.mark.anyio
async def test_delete_org_cascades_to_workspaces(db_session):
    """Deleting an org must delete its workspaces (no orphaned workspaces).

    Expected: passes (ondelete='CASCADE' already set on Workspace.organization_id FK).
    If it fails, add CASCADE to the FK and generate a migration.
    """
    # Organization requires: id, name, slug, owner_id
    owner_id = uuid.uuid4()
    # Insert a user first (owner_id FK)
    from app.db.models import User
    owner = User(id=owner_id, email=f"owner-{owner_id}@test.com", hashed_password="x")
    db_session.add(owner)
    await db_session.flush()

    org = Organization(
        id=uuid.uuid4(), name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}",
        owner_id=owner_id
    )
    db_session.add(org)
    await db_session.flush()

    ws = Workspace(
        id=uuid.uuid4(), name="Test WS",
        organization_id=org.id
    )
    db_session.add(ws)
    await db_session.flush()

    # Delete the org — cascade must propagate
    await db_session.delete(org)
    await db_session.flush()

    remaining = await db_session.scalar(
        select(Workspace).where(Workspace.id == ws.id)
    )
    assert remaining is None, (
        "Workspace must be deleted when its Organization is deleted. "
        "Add ondelete='CASCADE' to Workspace.organization_id FK."
    )
```

- [ ] **Step 2: Run test (verify current state)**

```bash
cd backend && uv run pytest tests/db/test_org_cascade_delete.py -v
```

**If test passes:** The cascade is already configured — commit only the test file with message:
`test(db): verify Organization→Workspace cascade delete (already correct)` and skip to the commit step.

**If test fails:** Proceed to Task 4 (add migration).

---

### Task 4: Fix cascade delete

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/<next>_fix_org_cascade_delete.py`

- [ ] **Step 1: Ensure database is running**

```bash
docker compose up -d postgres
```

- [ ] **Step 2: Update FK ondelete in Workspace model**

Find `Workspace.organization_id` FK in `models.py` and ensure:

```python
organization_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("organizations.id", ondelete="CASCADE"),  # was "SET NULL" or nothing
    nullable=False,
)
```

Also verify `WorkspaceMember.workspace_id` already has `ondelete="CASCADE"` (it should).

- [ ] **Step 3: Generate and verify migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "fix_org_cascade_delete"
```

Review generated file — upgrade must contain `ALTER TABLE ... DROP CONSTRAINT ... ADD CONSTRAINT ... ON DELETE CASCADE`.

- [ ] **Step 4: Apply and test**

```bash
cd backend && uv run alembic upgrade head
cd backend && uv run pytest tests/db/test_org_cascade_delete.py -v
```

- [ ] **Step 5: Full suite + static checks + commit**

```bash
cd backend && uv run pytest tests/ --tb=short 2>&1 | tail -10
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
git checkout -b fix/medium-db-org-cascade-delete dev
git add backend/app/db/models.py backend/alembic/versions/ backend/tests/db/test_org_cascade_delete.py
git commit -m "fix(db): add CASCADE delete from Organization to Workspaces"
```

---

## Chunk 3: PR-15 — WorkspaceSettings JSONB Schema Validation

**Branch:** `fix/medium-db-workspace-settings-jsonb`

### Task 5: Write failing test

**Files:**
- Test: `backend/tests/api/test_workspace_settings_validation.py` (new)

- [ ] **Step 1: Write test**

```python
# backend/tests/api/test_workspace_settings_validation.py
"""Test: WorkspaceSettings must reject unknown keys (extra='forbid')."""
import uuid
import pytest
from app.db.models import Organization, Workspace, WorkspaceMember


@pytest.mark.anyio
async def test_workspace_settings_rejects_unknown_keys(auth_client, db_session):
    """PUT /api/workspaces/{id}/settings with unknown keys must return 422.

    FAILS before fix: WorkspaceSettingsUpdate has no extra='forbid', unknown keys silently ignored.
    PASSES after fix: model_config = {'extra': 'forbid'} added to WorkspaceSettingsUpdate.
    """
    # Create workspace owned by current user
    resp = await auth_client.get("/api/auth/me")
    user_id = resp.json()["id"]

    owner = await db_session.get(type("User", (), {}), uuid.UUID(user_id))
    # Use direct SQL insert to avoid import issues:
    from app.db.models import User, Organization, Workspace, WorkspaceMember
    from sqlalchemy import select
    user_row = await db_session.scalar(select(User).where(User.id == uuid.UUID(user_id)))

    org = Organization(
        id=uuid.uuid4(), name="SettingsTestOrg",
        slug=f"settings-test-{uuid.uuid4().hex[:6]}", owner_id=uuid.UUID(user_id)
    )
    db_session.add(org)
    await db_session.flush()

    ws = Workspace(id=uuid.uuid4(), name="SettingsTestWS", organization_id=org.id)
    db_session.add(ws)
    await db_session.flush()

    member = WorkspaceMember(workspace_id=ws.id, user_id=uuid.UUID(user_id), role="owner")
    db_session.add(member)
    await db_session.flush()

    # Endpoint body is FLAT (WorkspaceSettingsUpdate fields directly, not nested)
    # Sending an unknown key must return 422 after fix
    resp = await auth_client.put(
        f"/api/workspaces/{ws.id}/settings",
        json={"__unknown_key__": "should_fail"},
    )
    # After fix: 422 Unprocessable Entity
    assert resp.status_code == 422, (
        f"Expected 422 for unknown field '__unknown_key__', got {resp.status_code}. "
        "Add model_config = {'extra': 'forbid'} to WorkspaceSettingsUpdate."
    )
```

- [ ] **Step 2: Run — FAIL (unknown keys are silently ignored)**

```bash
cd backend && uv run pytest tests/api/test_workspace_settings_validation.py -v
```

---

### Task 6: Create WorkspaceSettingsSchema and validate on save

**Files:**
- Create or modify: `backend/app/api/workspaces.py`

- [ ] **Step 1: Add `extra='forbid'` to existing schema**

In `backend/app/api/workspaces.py`, find the existing `WorkspaceSettingsUpdate` class (line ~155):

```python
class WorkspaceSettingsUpdate(BaseModel):
    model_config = {"extra": "forbid"}  # ADD this line — reject unknown keys
    model_provider: str | None = Field(default=None, max_length=50)
    model_name: str | None = Field(default=None, max_length=100)
    api_keys: dict[str, str | list[str]] | None = None
```

**Note:** The endpoint `PUT /api/workspaces/{ws_id}/settings` already accepts `body: WorkspaceSettingsUpdate` as a flat body (not nested). Do NOT add a wrapper class or change the endpoint signature — only add `model_config = {"extra": "forbid"}` to the existing schema.

- [ ] **Step 3: Test + static checks + commit**

```bash
cd backend && uv run pytest tests/api/test_workspace_settings_validation.py -v
cd backend && uv run pytest tests/ --tb=short 2>&1 | tail -10
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
git checkout -b fix/medium-db-workspace-settings-jsonb dev
git add backend/app/api/workspaces.py backend/tests/api/test_workspace_settings_validation.py
git commit -m "fix(api): add Pydantic schema validation for WorkspaceSettings JSONB field"
```

---

## Chunk 4: PR-16 — Admin Endpoints Missing Pagination Defaults (already covered in PR-06)

**Note:** PR-16 (admin pagination defaults) was partially addressed in Phase 2 PR-06. If all admin list endpoints already have `limit: int = Query(default=50, le=1000)` and `offset: int = Query(default=0, ge=0)` after PR-06, this PR can be verified and closed with a test-only commit.

**Branch:** `fix/medium-api-admin-pagination-defaults`

- [ ] **Step 1: Verify PR-06 already applied limits to ALL admin list endpoints**

```bash
cd backend && grep -n "le=1000\|ge=0" app/api/admin.py
```

If all list endpoints have these constraints, write a verification test and commit.

- [ ] **Step 2: Add any missing constraints and commit**

```bash
git checkout -b fix/medium-api-admin-pagination-defaults dev
# If no changes needed, create an empty commit with documentation:
git commit --allow-empty -m "docs(api): confirm all admin list endpoints have pagination limits (covered in PR-06)"
```

---

## Chunk 5: PR-17 — Document Upload Without Size Limit

**Branch:** `fix/medium-api-document-upload-size-limit`

### Task 7: Write failing test

**Files:**
- Test: `backend/tests/api/test_document_size_limit.py` (new)

- [ ] **Step 1: Write test**

```python
# backend/tests/api/test_document_size_limit.py
"""Test: document upload must reject files over MAX_DOCUMENT_SIZE_BYTES."""
import pytest
from io import BytesIO


@pytest.mark.anyio
async def test_upload_oversized_document_returns_413(auth_client):
    """Uploading a file larger than MAX_DOCUMENT_SIZE_BYTES must return 413.

    FAILS before fix: any size is accepted.
    PASSES after fix: size check at upload endpoint returns 413.
    """
    from app.core.config import settings

    # Create a file slightly over the limit
    oversized_content = b"x" * (getattr(settings, "max_document_size_bytes", 100_000_000) + 1)
    files = {"file": ("big.txt", BytesIO(oversized_content), "text/plain")}

    resp = await auth_client.post("/api/documents", files=files)
    assert resp.status_code == 413, (
        f"Expected 413 for oversized document, got {resp.status_code}. "
        "Add MAX_DOCUMENT_SIZE_BYTES config and check in upload handler."
    )
```

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/api/test_document_size_limit.py -v
```

---

### Task 8: Add size limit

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/documents.py`

- [ ] **Step 1: Add config**

```python
# In config.py:
max_document_size_bytes: int = Field(
    default=100_000_000,  # 100 MB
    description="Maximum allowed document upload size in bytes",
)
```

- [ ] **Step 2: Check size before MinIO upload in documents.py**

```python
# In the upload endpoint, after reading file content:
if len(content) > settings.max_document_size_bytes:
    raise HTTPException(
        status_code=413,
        detail=f"File too large. Maximum allowed size is {settings.max_document_size_bytes // 1_000_000} MB.",
    )
```

- [ ] **Step 3: Test + static checks + commit**

```bash
cd backend && uv run pytest tests/api/test_document_size_limit.py -v
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
git checkout -b fix/medium-api-document-upload-size-limit dev
git add backend/app/core/config.py backend/app/api/documents.py \
        backend/tests/api/test_document_size_limit.py
git commit -m "fix(api): reject document uploads exceeding MAX_DOCUMENT_SIZE_BYTES with HTTP 413"
```

---

## Chunk 6: PR-18 — MCP Tools Create New Process Per Invocation

**Branch:** `fix/medium-tools-mcp-connection-reuse`

### Task 9: Write failing test

**Files:**
- Read: `backend/app/tools/` (find MCP client file)
- Test: `backend/tests/tools/test_mcp_connection_reuse.py` (new)

- [ ] **Step 1: Find MCP client**

```bash
cd backend && find app/tools -name "*.py" | xargs grep -l "stdio\|mcp\|subprocess" 2>/dev/null | head -5
```

- [ ] **Step 2: Write test**

```python
# backend/tests/tools/test_mcp_connection_reuse.py
"""Test: MCP tools must reuse stdio connections within the same agent session."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


@pytest.mark.anyio
async def test_mcp_connection_reused_within_session():
    """Two tool calls with the same session_id must reuse the same connection.

    FAILS before fix: new subprocess created per call.
    PASSES after fix: connection pool keyed by agent_session_id.
    """
    try:
        from app.tools.mcp_client import MCPConnectionPool
    except ImportError:
        pytest.skip("MCPConnectionPool not implemented yet")

    pool = MCPConnectionPool()
    session_id = "test-session-abc"

    mock_conn = AsyncMock()
    mock_conn.is_alive = MagicMock(return_value=True)

    with patch.object(pool, "_create_connection", AsyncMock(return_value=mock_conn)) as mock_create:
        conn1 = await pool.get_or_create(session_id, server_name="test_server")
        conn2 = await pool.get_or_create(session_id, server_name="test_server")

    # Must have created only 1 connection (reused on second call)
    assert mock_create.call_count == 1, (
        f"Expected 1 connection creation, got {mock_create.call_count}. "
        "Connections must be reused within the same agent session."
    )
    assert conn1 is conn2
```

- [ ] **Step 3: Run — SKIP (MCPConnectionPool doesn't exist yet)**

```bash
cd backend && uv run pytest tests/tools/test_mcp_connection_reuse.py -v
```

---

### Task 10: Implement connection pool

**Files:**
- Modify or create: relevant MCP client file

- [ ] **Step 1: Add MCPConnectionPool class**

Find the MCP client file from Task 9 Step 1. Add a `MCPConnectionPool` class:

```python
class MCPConnectionPool:
    """Per-agent-session stdio connection pool for MCP servers."""

    def __init__(self) -> None:
        self._pool: dict[str, dict[str, Any]] = {}  # {session_id: {server_name: conn}}

    async def get_or_create(self, session_id: str, server_name: str) -> Any:
        if session_id not in self._pool:
            self._pool[session_id] = {}
        if server_name not in self._pool[session_id]:
            conn = await self._create_connection(server_name)
            self._pool[session_id][server_name] = conn
        return self._pool[session_id][server_name]

    async def close_session(self, session_id: str) -> None:
        """Close all connections for a session (call in agent runner finally block)."""
        if session_id in self._pool:
            for conn in self._pool[session_id].values():
                try:
                    await conn.close()
                except Exception:
                    pass
            del self._pool[session_id]

    async def _create_connection(self, server_name: str) -> Any:
        # Existing stdio process creation logic goes here
        ...
```

- [ ] **Step 2: Test + static checks + commit**

```bash
cd backend && uv run pytest tests/tools/test_mcp_connection_reuse.py -v
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
git checkout -b fix/medium-tools-mcp-connection-reuse dev
git add backend/app/tools/ backend/tests/tools/test_mcp_connection_reuse.py
git commit -m "fix(tools): add MCPConnectionPool to reuse stdio connections within agent session"
```

---

## Chunk 7: PR-19 — CronJob Missing Unique Name Constraint

**Branch:** `fix/medium-db-cronjob-unique-name`

### Task 11: Write failing test + fix

**Files:**
- Test: `backend/tests/db/test_cronjob_unique_name.py` (new)
- Modify: `backend/app/db/models.py`
- Create: migration

- [ ] **Step 1: Write test**

```python
# backend/tests/db/test_cronjob_unique_name.py
"""Test: CronJob names must be unique per user."""
import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from app.db.models import CronJob


@pytest.mark.anyio
async def test_cronjob_name_unique_per_user(db_session):
    """Two cron jobs with the same name for the same user must raise IntegrityError.

    FAILS before fix: no unique constraint.
    PASSES after fix: UniqueConstraint('user_id', 'name') added.
    """
    user_id = uuid.uuid4()
    job1 = CronJob(
        id=uuid.uuid4(), user_id=user_id, name="daily-report",
        schedule="0 9 * * *", task="Send report", trigger_type="cron",
    )
    job2 = CronJob(
        id=uuid.uuid4(), user_id=user_id, name="daily-report",
        schedule="0 10 * * *", task="Another report", trigger_type="cron",
    )
    db_session.add(job1)
    await db_session.flush()
    db_session.add(job2)

    with pytest.raises(IntegrityError):
        await db_session.flush()
```

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/db/test_cronjob_unique_name.py -v
```

- [ ] **Step 3: Add UniqueConstraint to CronJob model**

```python
# In CronJob model __table_args__:
__table_args__ = (
    UniqueConstraint("user_id", "name", name="uq_cronjob_user_name"),
)
```

- [ ] **Step 4: Generate migration, verify, apply, test**

```bash
docker compose up -d postgres
cd backend && uv run alembic revision --autogenerate -m "add_unique_cronjob_name_per_user"
# Review generated migration file
cd backend && uv run alembic upgrade head
cd backend && uv run pytest tests/db/test_cronjob_unique_name.py -v
```

- [ ] **Step 5: Static checks + commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
git checkout -b fix/medium-db-cronjob-unique-name dev
git add backend/app/db/models.py backend/alembic/versions/ backend/tests/db/test_cronjob_unique_name.py
git commit -m "fix(db): add unique constraint on (user_id, name) for CronJob"
```

---

## Chunk 8: PR-20 — WebhookDelivery Response Body Unbounded

**Branch:** `fix/medium-db-webhook-delivery-truncate`

### Task 12: Write failing test + fix

**Files:**
- Test: `backend/tests/test_webhook_delivery_truncate.py` (new)
- Modify: `backend/app/worker.py`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Write test**

```python
# backend/tests/test_webhook_delivery_truncate.py
"""Test: webhook response body must be truncated to MAX_WEBHOOK_RESPONSE_BYTES."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def test_response_body_truncated_to_limit():
    """The deliver_webhook function must truncate response_body before saving.

    FAILS before fix: full response stored regardless of size.
    PASSES after fix: response truncated to settings.max_webhook_response_bytes.
    """
    from app.core.config import settings
    limit = getattr(settings, "max_webhook_response_bytes", 10_240)

    # Simulate a 1MB response body
    large_body = "x" * 1_000_000

    # Import and test the truncation helper
    try:
        from app.worker import _truncate_response_body
        result = _truncate_response_body(large_body)
        assert len(result) <= limit, (
            f"Expected truncated to {limit} chars, got {len(result)}"
        )
    except ImportError:
        pytest.fail(
            "_truncate_response_body not found in app.worker. "
            "Add this helper function that truncates to settings.max_webhook_response_bytes."
        )
```

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/test_webhook_delivery_truncate.py -v
```

- [ ] **Step 3: Add config and helper function**

In `config.py`:
```python
max_webhook_response_bytes: int = Field(
    default=10_240, description="Maximum bytes to store for webhook response body"
)
```

In `worker.py`:
```python
def _truncate_response_body(body: str) -> str:
    """Truncate response body to settings.max_webhook_response_bytes."""
    limit = settings.max_webhook_response_bytes
    if len(body) > limit:
        return body[:limit] + f"... [truncated at {limit} bytes]"
    return body
```

Use `_truncate_response_body(response_text)` before saving to `WebhookDelivery.response_body`.

- [ ] **Step 4: Test + static checks + commit**

```bash
cd backend && uv run pytest tests/test_webhook_delivery_truncate.py -v
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
git checkout -b fix/medium-db-webhook-delivery-truncate dev
git add backend/app/worker.py backend/app/core/config.py backend/tests/test_webhook_delivery_truncate.py
git commit -m "fix(worker): truncate WebhookDelivery response_body to MAX_WEBHOOK_RESPONSE_BYTES"
```

---

## Chunk 9: PR-21 — Cron Schedule Syntax Not Validated at Creation

**Branch:** `fix/medium-scheduler-cron-syntax-validate`

### Task 13: Write failing test + fix

**Files:**
- Test: `backend/tests/api/test_cron_schedule_validation.py` (new)
- Modify: `backend/app/api/cron.py`

- [ ] **Step 1: Write test**

```python
# backend/tests/api/test_cron_schedule_validation.py
"""Test: invalid cron schedule must be rejected at creation time."""
import pytest


@pytest.mark.anyio
async def test_create_cron_job_rejects_invalid_schedule(auth_client):
    """POST /api/cron with invalid schedule must return 400.

    FAILS before fix: invalid schedule is saved, fails later at runtime.
    PASSES after fix: schedule is validated before saving.
    """
    resp = await auth_client.post(
        "/api/cron",
        json={
            "schedule": "not-a-valid-cron",
            "task": "Do something",
            "trigger_type": "cron",
        },
    )
    assert resp.status_code == 400, (
        f"Expected 400 for invalid schedule 'not-a-valid-cron', got {resp.status_code}. "
        "Validate cron schedule syntax in POST /api/cron before saving."
    )
    assert "schedule" in resp.json().get("detail", "").lower() or \
           "invalid" in resp.json().get("detail", "").lower()
```

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/api/test_cron_schedule_validation.py -v
```

- [ ] **Step 3: Add validation in cron.py**

In the `POST /api/cron` handler, before saving:

```python
from app.scheduler.runner import parse_trigger

# Validate schedule before saving
# parse_trigger signature: (schedule_str: str, start_date: datetime | None = None)
try:
    parse_trigger(data.schedule)
except (ValueError, Exception) as exc:
    raise HTTPException(
        status_code=400,
        detail=f"Invalid schedule '{data.schedule}': {exc}",
    )
```

- [ ] **Step 4: Test + static checks + commit**

```bash
cd backend && uv run pytest tests/api/test_cron_schedule_validation.py -v
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
git checkout -b fix/medium-scheduler-cron-syntax-validate dev
git add backend/app/api/cron.py backend/tests/api/test_cron_schedule_validation.py
git commit -m "fix(scheduler): validate cron schedule syntax at creation time, return 400 on invalid"
```

---

## Chunk 10: PR-22 — Frontend 429 Rate Limit Error Handling

**Branch:** `fix/medium-frontend-429-rate-limit-ux`

### Task 14: Fix frontend 429 handling

**Files:**
- Modify: `frontend/src/api/client.ts`
- Read: `frontend/src/composables/useToast.ts` (verify toast API)

- [ ] **Step 1: Check existing error interceptor**

```bash
grep -n "interceptors\|401\|status" frontend/src/api/client.ts | head -20
```

- [ ] **Step 2: Add 429 handling to Axios response interceptor**

In `frontend/src/api/client.ts`, add the import at the top and add 429 handling in the error interceptor:

```typescript
// At top of file, add import:
import { useToast } from '@/composables/useToast'

// In the response error interceptor:
if (error.response?.status === 429) {
  const retryAfter = error.response.headers['retry-after']
  const waitSeconds = retryAfter ? parseInt(retryAfter, 10) : 60
  // useToast() works outside Vue components: toasts ref is module-level
  // API: { success, error, info } — use info() for rate limit warnings
  useToast().info(`请求过于频繁，请等待 ${waitSeconds} 秒后重试`)
}
```

- [ ] **Step 3: Add TypeScript type check**

```bash
cd frontend && bun run type-check
```

- [ ] **Step 4: Lint + commit**

```bash
cd frontend && bun run lint:fix && bun run type-check
git checkout -b fix/medium-frontend-429-rate-limit-ux dev
git add frontend/src/api/client.ts
git commit -m "fix(frontend): show user-friendly toast when API rate limit (429) is hit"
```

---

## Chunk 11: PR-23 — Missing Environment Variable Validation at Startup

**Branch:** `fix/medium-core-env-var-startup-validation`

### Task 15: Write failing test + fix

**Files:**
- Test: `backend/tests/test_startup_validation.py` (new)
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Write test**

```python
# backend/tests/test_startup_validation.py
"""Test: missing required env vars must cause immediate startup failure."""
import pytest
from unittest.mock import patch


def test_missing_jwt_secret_raises_on_import():
    """If JWT_SECRET is not set, app startup must fail immediately with a clear error.

    FAILS before fix: app starts with None JWT_SECRET, fails on first request.
    PASSES after fix: startup validation raises ValueError on missing secrets.
    """
    # This test verifies the validation function exists
    try:
        from app.core.config import validate_required_settings
    except ImportError:
        pytest.fail(
            "validate_required_settings not found in app.core.config. "
            "Add this function that checks all required settings are present."
        )

    # Test with a mock settings that has missing critical fields
    mock_settings = type("MockSettings", (), {
        "jwt_secret": None,
        "encryption_key": "valid-key",
    })()

    with pytest.raises((ValueError, RuntimeError)) as exc_info:
        validate_required_settings(mock_settings)

    assert "jwt" in str(exc_info.value).lower() or "secret" in str(exc_info.value).lower()
```

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/test_startup_validation.py -v
```

- [ ] **Step 3: Add validation function**

In `config.py`:

```python
def validate_required_settings(s: "Settings | None" = None) -> None:
    """Raise ValueError if any critical setting is missing.

    Called from app lifespan on startup.
    """
    cfg = s or settings
    missing = []
    if not getattr(cfg, "jwt_secret", None):
        missing.append("JWT_SECRET")
    if not getattr(cfg, "encryption_key", None):
        missing.append("ENCRYPTION_KEY")
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Run 'bash scripts/init-env.sh' to generate them."
        )
```

In `main.py` lifespan:

```python
from app.core.config import validate_required_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_required_settings()  # Fail fast on missing config
    ...
```

- [ ] **Step 4: Test + static checks + commit**

```bash
cd backend && uv run pytest tests/test_startup_validation.py -v
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
git checkout -b fix/medium-core-env-var-startup-validation dev
git add backend/app/core/config.py backend/app/main.py backend/tests/test_startup_validation.py
git commit -m "fix(core): add startup validation for required env vars (JWT_SECRET, ENCRYPTION_KEY)"
```

---

## Phase 3 Completion Checklist

- [ ] PR-13: `fix/medium-core-exception-no-recovery` — merged to dev
- [ ] PR-14: `fix/medium-db-org-cascade-delete` — merged to dev
- [ ] PR-15: `fix/medium-db-workspace-settings-jsonb` — merged to dev
- [ ] PR-16: `fix/medium-api-admin-pagination-defaults` — merged to dev (or confirmed covered by PR-06)
- [ ] PR-17: `fix/medium-api-document-upload-size-limit` — merged to dev
- [ ] PR-18: `fix/medium-tools-mcp-connection-reuse` — merged to dev
- [ ] PR-19: `fix/medium-db-cronjob-unique-name` — merged to dev
- [ ] PR-20: `fix/medium-db-webhook-delivery-truncate` — merged to dev
- [ ] PR-21: `fix/medium-scheduler-cron-syntax-validate` — merged to dev
- [ ] PR-22: `fix/medium-frontend-429-rate-limit-ux` — merged to dev
- [ ] PR-23: `fix/medium-core-env-var-startup-validation` — merged to dev

**Next:** Execute `docs/superpowers/plans/2026-03-16-jarvis-quality-phase4-low.md`
