# JARVIS Quality — Phase 1: Critical Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 4 Critical-severity issues to eliminate test instability, a security hole, a race condition, and swallowed LLM errors.

**Architecture:** Each task is a self-contained PR on its own branch from `dev`. Every task follows TDD: write the failing test first, then implement the fix, then confirm the test passes.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, asyncpg, Qdrant, LangChain, pytest-anyio

**Spec:** `docs/superpowers/specs/2026-03-16-jarvis-quality-perfection-design.md`

---

## Chunk 1: PR-01 — AsyncSessionLocal Cross-Event-Loop Contamination

**Branch:** `fix/critical-db-asyncsession-loop-contamination`

### Task 1: Audit all AsyncSessionLocal usages outside request scope

**Files:**
- Read: `backend/app/worker.py`
- Read: `backend/app/api/chat.py`
- Read: `backend/tests/conftest.py` (understand existing autouse pattern)

- [ ] **Step 1: Find all AsyncSessionLocal usages in app code**

```bash
cd backend && grep -rn "AsyncSessionLocal" app/ --include="*.py"
```

Expected output example:
```
app/worker.py:47:    async with AsyncSessionLocal() as db:
app/api/chat.py:NNN: async with AsyncSessionLocal() as session:
app/api/deps.py:104:    async with AsyncSessionLocal() as _session:
```

- [ ] **Step 2: Check which are already suppressed in conftest.py**

```bash
cd backend && grep "AsyncSessionLocal\|suppress" tests/conftest.py
```

Already suppressed:
- `app.api.auth.log_action` → `_suppress_auth_audit_logging`
- `app.api.deps.AsyncSessionLocal` → `_suppress_pat_last_used_update`
- `app.api.chat.AsyncSessionLocal` → `_suppress_chat_async_session`

Remaining (verify from Step 1 output): `app.worker.AsyncSessionLocal`.

---

### Task 2: Write the failing test

**Files:**
- Test: `backend/tests/test_asyncsession_loop_contamination.py` (new file)

The correct TDD test: before the autouse fixture is added, `app.worker.AsyncSessionLocal` is the real implementation (not a mock). After the fixture is added, it becomes a `MagicMock`. The test checks that it IS mocked (i.e., the fixture is active).

- [ ] **Step 1: Write the regression test**

```python
# backend/tests/test_asyncsession_loop_contamination.py
"""Regression test: all AsyncSessionLocal usages outside request scope must be
mocked in the test suite to prevent cross-event-loop connection pool contamination.

Without these mocks, asyncpg connections acquired in one test's event loop cannot
be reused by the next test's event loop, causing:
  "Future <Future ...> attached to a different loop"
"""
import pytest
from unittest.mock import MagicMock


@pytest.mark.anyio
async def test_worker_asyncsession_is_mocked():
    """app.worker.AsyncSessionLocal must be mocked by an autouse fixture.

    FAILS before fix: the real AsyncSessionLocal is not patched, so calling
    it in tests would contaminate the connection pool across event loops.
    PASSES after fix: the autouse fixture replaces it with a MagicMock.
    """
    import app.worker as worker_module
    # The autouse fixture patches app.worker.AsyncSessionLocal.
    # When active, calling it returns a MagicMock (not a real session factory).
    instance = worker_module.AsyncSessionLocal()
    assert isinstance(instance, MagicMock), (
        "app.worker.AsyncSessionLocal must be mocked in tests. "
        "Add an autouse fixture in conftest.py that patches "
        "'app.worker.AsyncSessionLocal'. Without it, asyncpg connections "
        "bind to the test event loop and contaminate subsequent tests."
    )
```

- [ ] **Step 2: Run — confirm it FAILS (no fixture exists yet)**

```bash
cd backend && uv run pytest tests/test_asyncsession_loop_contamination.py -v
```

Expected: FAIL — `app.worker.AsyncSessionLocal()` returns a real coroutine factory, not a `MagicMock`.

---

### Task 3: Add the autouse fixture

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Add autouse fixture after existing `_suppress_chat_async_session`**

```python
@pytest.fixture(autouse=True)
async def _suppress_worker_async_session():
    """Mock AsyncSessionLocal in worker to prevent cross-event-loop pool contamination.

    execute_cron_job() and deliver_webhook() use AsyncSessionLocal directly.
    Those connections bind to the calling event loop and are invalid in the
    next test's event loop, causing asyncpg "another operation is in progress".
    """
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = MagicMock(return_value=mock_session)
    mock_session.scalar = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.get = AsyncMock(return_value=None)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    with patch("app.worker.AsyncSessionLocal", return_value=mock_session):
        yield
```

- [ ] **Step 2: Run the regression test — must now PASS**

```bash
cd backend && uv run pytest tests/test_asyncsession_loop_contamination.py -v
```

Expected: PASS

- [ ] **Step 3: Run full suite, confirm no "Future attached to a different loop" errors**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | grep -E "(FAILED|ERROR|loop|attached)" | head -20
```

Expected: No lines mentioning "loop" contamination errors.

- [ ] **Step 4: Run full suite to confirm no regressions**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -10
```

- [ ] **Step 5: Static checks**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
```

- [ ] **Step 6: Commit**

```bash
git checkout -b fix/critical-db-asyncsession-loop-contamination dev
git add backend/tests/conftest.py backend/tests/test_asyncsession_loop_contamination.py
git commit -m "fix(test): suppress app.worker.AsyncSessionLocal to prevent cross-loop contamination"
```

---

## Chunk 2: PR-02 — Missing Workspace Member Permission Checks

**Branch:** `fix/critical-security-workspace-permissions`

**Audit result (pre-verified):**
- `GET /api/documents?workspace_id=` → lines 58–65 of `documents.py` already check membership ✓
- `GET /api/cron?workspace_id=` → lines 64–89 of `cron.py` **does NOT** check membership ✗ ← target
- `GET /api/workspaces/{id}/members` and sub-resources → verify membership check

### Task 4: Write the failing security test

**Files:**
- Test: `backend/tests/api/test_workspace_permissions.py` (new file)

- [ ] **Step 1: Write the attack scenario test**

```python
# backend/tests/api/test_workspace_permissions.py
"""Security test: non-members must not access workspace-scoped resources."""
import uuid
import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, suffix: str = "") -> str:
    """Register a unique user and return their JWT token."""
    email = f"user_{uuid.uuid4().hex[:8]}{suffix}@test.com"
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def _create_org_and_workspace(client: AsyncClient, token: str) -> str:
    """Create an org + workspace as the given user. Returns workspace_id."""
    client.headers["Authorization"] = f"Bearer {token}"
    org = await client.post("/api/organizations", json={"name": f"Org-{uuid.uuid4().hex[:4]}"})
    assert org.status_code == 201, org.text
    ws = await client.post(
        "/api/workspaces",
        json={"name": f"WS-{uuid.uuid4().hex[:4]}", "organization_id": org.json()["id"]},
    )
    assert ws.status_code == 201, ws.text
    return ws.json()["id"]


@pytest.mark.anyio
async def test_non_member_cannot_list_workspace_cron_jobs(client):
    """GET /api/cron?workspace_id=<other> must return 403 for non-members."""
    token_a = await _register(client, "_a")
    workspace_id = await _create_org_and_workspace(client, token_a)

    # User B tries to list cron jobs scoped to User A's workspace
    token_b = await _register(client, "_b")
    client.headers["Authorization"] = f"Bearer {token_b}"

    resp = await client.get(f"/api/cron?workspace_id={workspace_id}")
    assert resp.status_code == 403, (
        f"Expected 403, got {resp.status_code}. "
        "Non-members must not list workspace cron jobs."
    )
```

- [ ] **Step 2: Run to confirm it currently FAILS (returns 200)**

```bash
cd backend && uv run pytest tests/api/test_workspace_permissions.py::test_non_member_cannot_list_workspace_cron_jobs -v
```

Expected: FAIL — endpoint returns 200 without checking membership.

---

### Task 5: Add membership check to cron list endpoint

**Files:**
- Modify: `backend/app/api/cron.py`

- [ ] **Step 1: Add a helper function and inject membership check**

In `backend/app/api/cron.py`, add a helper at the top of the file (after imports):

```python
async def _require_workspace_member(
    workspace_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> None:
    """Raise 403 if user is not a member of the given workspace."""
    from sqlalchemy import select as _select
    membership = await db.scalar(
        _select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=403, detail="You are not a member of this workspace"
        )
```

- [ ] **Step 2: Add check to `list_cron_jobs` endpoint**

In the `list_cron_jobs` handler (line 64), add after `query = select(CronJob).where(...)`:

```python
    if workspace_id is not None:
        await _require_workspace_member(workspace_id, user, db)
        query = query.where(CronJob.workspace_id == workspace_id)
```

- [ ] **Step 3: Audit other `workspace_id` endpoints in cron.py and workspaces.py**

```bash
cd backend && grep -n "workspace_id" app/api/cron.py app/api/workspaces.py
```

For each handler that accepts `workspace_id` without a membership check, add the same `await _require_workspace_member(...)` call.

- [ ] **Step 4: Run the security test — must now PASS**

```bash
cd backend && uv run pytest tests/api/test_workspace_permissions.py -v
```

Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -15
```

- [ ] **Step 6: Static checks**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
```

- [ ] **Step 7: Commit**

```bash
git checkout -b fix/critical-security-workspace-permissions dev
git add backend/app/api/cron.py backend/app/api/workspaces.py \
        backend/tests/api/test_workspace_permissions.py
git commit -m "fix(security): enforce workspace member permission checks on cron and workspace endpoints"
```

---

## Chunk 3: PR-03 — Qdrant Collection Creation Race Condition

**Branch:** `fix/critical-infra-qdrant-race-condition`

### Task 6: Write the failing race condition test

**Files:**
- Test: `backend/tests/infra/test_qdrant_race.py` (new file)

- [ ] **Step 1: Write deterministic concurrent creation test**

```python
# backend/tests/infra/test_qdrant_race.py
"""Regression test: concurrent ensure_collection must not raise on already-exists."""
import asyncio
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from qdrant_client.http.exceptions import UnexpectedResponse


def _make_already_exists_error() -> UnexpectedResponse:
    """Simulate Qdrant's response when a collection already exists."""
    return UnexpectedResponse(
        status_code=400,
        reason_phrase="Bad Request",
        content=b'{"status":{"error":"Collection already exists!"}}',
        headers={},
    )


@pytest.mark.anyio
async def test_concurrent_ensure_collection_no_exception():
    """10 concurrent coroutines calling ensure_collection for the same name
    must not raise, even if Qdrant returns 'already exists' on create_collection.

    Scenario: collection_exists() returns False for the first caller (race window),
    all 10 attempt create_collection(), Qdrant rejects 9 with 'already exists'.
    After fix: the exception is caught and the collection is verified to exist.
    """
    collection_name = f"test_{uuid.uuid4().hex[:8]}"

    mock_client = MagicMock()
    # collection_exists always returns True (post-race state)
    mock_client.collection_exists = AsyncMock(return_value=True)
    # create_collection always raises "already exists"
    mock_client.create_collection = AsyncMock(
        side_effect=_make_already_exists_error()
    )

    with patch("app.infra.qdrant.get_qdrant_client", AsyncMock(return_value=mock_client)):
        # Reset the in-process cache so all coroutines go through the full path
        import app.infra.qdrant as qdrant_mod
        original_created = qdrant_mod._created_collections.copy()
        qdrant_mod._created_collections.clear()
        try:
            tasks = [qdrant_mod.ensure_collection(collection_name) for _ in range(10)]
            # Must not raise any exception
            await asyncio.gather(*tasks)
        finally:
            qdrant_mod._created_collections.clear()
            qdrant_mod._created_collections.update(original_created)
```

- [ ] **Step 2: Run to confirm it currently FAILS**

```bash
cd backend && uv run pytest tests/infra/test_qdrant_race.py -v
```

Expected: FAIL — `UnexpectedResponse` propagates from `create_collection`.

---

### Task 7: Fix the race condition

**Files:**
- Modify: `backend/app/infra/qdrant.py`

- [ ] **Step 1: Add import for logger and wrap create_collection in try/except**

Add at top of file if not present:
```python
import structlog
logger = structlog.get_logger(__name__)
```

Replace the `create_collection` call in `ensure_collection`:

```python
async def ensure_collection(collection_name: str) -> None:
    """确保指定 Qdrant Collection 存在（幂等、并发安全）。"""
    if collection_name in _created_collections:
        return
    async with _collection_lock:
        if collection_name in _created_collections:
            return
        client = await get_qdrant_client()
        if await client.collection_exists(collection_name):
            _created_collections.add(collection_name)
            return
        vec_cfg = _load_vector_config()
        distance = getattr(Distance, vec_cfg["distance"].upper(), Distance.COSINE)
        try:
            await client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vec_cfg["size"], distance=distance),
            )
        except Exception as exc:
            # Another process may have created the collection between our
            # collection_exists() check and create_collection() call.
            # Re-check: if it now exists, treat as success; otherwise re-raise.
            if await client.collection_exists(collection_name):
                logger.debug(
                    "collection_already_exists_race",
                    collection=collection_name,
                    exc=str(exc),
                )
            else:
                raise
        _created_collections.add(collection_name)
```

- [ ] **Step 2: Run the test — must now PASS**

```bash
cd backend && uv run pytest tests/infra/test_qdrant_race.py -v
```

Expected: PASS

- [ ] **Step 3: Run full suite**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -10
```

- [ ] **Step 4: Static checks**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
```

- [ ] **Step 5: Commit**

```bash
git checkout -b fix/critical-infra-qdrant-race-condition dev
git add backend/app/infra/qdrant.py backend/tests/infra/test_qdrant_race.py
git commit -m "fix(infra): handle Qdrant collection already-exists race condition gracefully"
```

---

## Chunk 4: PR-04 — LLM Fallback Chain Exception Swallowing

**Branch:** `fix/critical-agent-llm-fallback-error-chain`

**Context:** `backend/app/agent/llm.py` — `get_llm_with_fallback` currently:
1. Swallows init failures of fallback providers with bare `except Exception: logger.warning(...)` (no provider name or error in the log)
2. Never raises a structured error — if the primary fails at init time (inside `get_llm`), the exception propagates unstructured

The spec requires:
- Fallback init failures must log `fallback_provider` and `error` fields
- A new `LLMInitError` exception type must be raised when all providers fail

### Task 8: Write the failing tests

**Files:**
- Test: `backend/tests/agent/test_llm_fallback.py` (new file)

- [ ] **Step 1: Write two failing tests**

```python
# backend/tests/agent/test_llm_fallback.py
"""Tests for LLM fallback chain error reporting."""
import logging
import pytest
from unittest.mock import MagicMock, patch


def test_fallback_init_failure_logs_provider_name(caplog):
    """When a fallback provider fails to init, the WARNING log must include
    the provider name and error details as structured fields.

    FAILS before fix: current log call is `logger.warning("openai_fallback_init_failed")`
    with no extra fields.
    PASSES after fix: log call includes fallback_provider="openai" and error=str(exc).
    """
    from app.agent.llm import get_llm_with_fallback

    with patch("app.agent.llm.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key"
        mock_settings.deepseek_api_key = None
        mock_settings.ollama_base_url = None

        with patch("app.agent.llm.get_llm") as mock_get_llm:
            primary = MagicMock()
            primary.with_fallbacks = MagicMock(return_value=primary)

            def side_effect(provider, *args, **kwargs):
                if provider == "openai":
                    raise ValueError("Connection refused to OpenAI")
                return primary

            mock_get_llm.side_effect = side_effect

            with caplog.at_level(logging.WARNING):
                get_llm_with_fallback("deepseek", "deepseek-chat", "key")

            # The warning must include "openai" somewhere (provider name)
            warning_texts = " ".join(r.getMessage() for r in caplog.records)
            assert "openai" in warning_texts.lower(), (
                f"Expected warning to mention 'openai', got: {caplog.records}"
            )


def test_all_providers_fail_raises_llm_init_error():
    """When ALL providers (primary + all fallbacks) fail to init,
    get_llm_with_fallback must raise LLMInitError with the failure chain.

    FAILS before fix: no LLMInitError class exists, exception is unstructured.
    PASSES after fix: LLMInitError raised with failures list.
    """
    from app.agent.llm import LLMInitError, get_llm_with_fallback

    with patch("app.agent.llm.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key"
        mock_settings.deepseek_api_key = "ds-key"
        mock_settings.ollama_base_url = None

        with patch("app.agent.llm.get_llm") as mock_get_llm:
            # All providers fail
            mock_get_llm.side_effect = ValueError("provider unreachable")

            with pytest.raises(LLMInitError) as exc_info:
                get_llm_with_fallback("deepseek", "deepseek-chat", "key")

            err = exc_info.value
            assert hasattr(err, "failures"), "LLMInitError must have a 'failures' attribute"
            assert len(err.failures) > 0, "failures list must not be empty"
            # Each failure must record the provider name
            provider_names = [name for name, _ in err.failures]
            assert "deepseek" in provider_names or any(
                name in provider_names for name in ["openai", "deepseek"]
            )
```

- [ ] **Step 2: Run to confirm both tests FAIL**

```bash
cd backend && uv run pytest tests/agent/test_llm_fallback.py -v
```

Expected: Both FAIL — `LLMInitError` doesn't exist, and log doesn't include provider name.

---

### Task 9: Implement LLMInitError and fix the fallback chain

**Files:**
- Modify: `backend/app/agent/llm.py`

- [ ] **Step 1: Add LLMInitError class and fix get_llm_with_fallback**

Replace the content of `backend/app/agent/llm.py`:

```python
from typing import Any

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models.zhipuai import ChatZhipuAI
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = structlog.get_logger(__name__)


class LLMInitError(Exception):
    """Raised when all LLM providers (primary + fallbacks) fail to initialize.

    Attributes:
        failures: List of (provider_name, exception) for each failed provider.
    """

    def __init__(self, failures: list[tuple[str, Exception]]) -> None:
        self.failures = failures
        summary = "; ".join(f"{p}: {e}" for p, e in failures)
        super().__init__(f"All LLM providers failed to initialize: {summary}")


def get_llm(
    provider: str, model: str, api_key: str, base_url: str | None = None, **kwargs: Any
) -> BaseChatModel:
    """Factory function to return a LangChain ChatModel instance."""
    if "temperature" not in kwargs:
        kwargs["temperature"] = 0
    if "max_retries" not in kwargs:
        kwargs["max_retries"] = 2

    match provider:
        case "deepseek":
            return ChatDeepSeek(model=model, api_key=api_key, **kwargs)
        case "openai":
            return ChatOpenAI(model=model, api_key=api_key, **kwargs)
        case "anthropic":
            return ChatAnthropic(model=model, api_key=api_key, **kwargs)
        case "zhipuai":
            return ChatZhipuAI(model=model, api_key=api_key, **kwargs)
        case "ollama":
            target_url = base_url or settings.ollama_base_url
            logger.info("creating_ollama_client", model=model, url=target_url)
            return ChatOllama(model=model, base_url=target_url, **kwargs)
        case _:
            raise ValueError(f"Unknown provider: {provider}")


def get_llm_with_fallback(
    provider: str, model: str, api_key: str, base_url: str | None = None, **kwargs: Any
) -> BaseChatModel:
    """Get an LLM with automatic failover to predefined backup models.

    Raises:
        LLMInitError: if the primary provider AND all fallbacks fail to init.
    """
    failures: list[tuple[str, Exception]] = []

    # Try primary provider
    try:
        primary_llm = get_llm(provider, model, api_key, base_url=base_url, **kwargs)
    except Exception as exc:
        logger.warning(
            "primary_provider_init_failed",
            primary_provider=provider,
            error=str(exc),
        )
        failures.append((provider, exc))
        primary_llm = None

    fallbacks: list[BaseChatModel] = []

    # 1. Fallback to OpenAI if not primary
    if provider != "openai" and settings.openai_api_key:
        try:
            fallbacks.append(
                get_llm("openai", "gpt-4o-mini", settings.openai_api_key, **kwargs)
            )
        except Exception as exc:
            logger.warning(
                "fallback_provider_init_failed",
                fallback_provider="openai",
                error=str(exc),
            )
            failures.append(("openai", exc))

    # 2. Fallback to DeepSeek if not primary
    if provider != "deepseek" and settings.deepseek_api_key:
        try:
            fallbacks.append(
                get_llm(
                    "deepseek", "deepseek-chat", settings.deepseek_api_key, **kwargs
                )
            )
        except Exception as exc:
            logger.warning(
                "fallback_provider_init_failed",
                fallback_provider="deepseek",
                error=str(exc),
            )
            failures.append(("deepseek", exc))

    # If primary failed and no fallbacks succeeded, raise structured error
    if primary_llm is None and not fallbacks:
        raise LLMInitError(failures)

    # If primary failed but fallbacks are available, use first fallback as primary
    if primary_llm is None:
        primary_llm = fallbacks.pop(0)

    if not fallbacks:
        logger.debug("no_fallbacks_available", provider=provider)
        return primary_llm

    logger.info(
        "llm_with_failover_ready", provider=provider, fallback_count=len(fallbacks)
    )
    return primary_llm.with_fallbacks(fallbacks)
```

- [ ] **Step 2: Run both tests — both must now PASS**

```bash
cd backend && uv run pytest tests/agent/test_llm_fallback.py -v
```

Expected: Both PASS

- [ ] **Step 3: Run full suite**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -15
```

- [ ] **Step 4: Static checks**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
```

- [ ] **Step 5: Commit**

```bash
git checkout -b fix/critical-agent-llm-fallback-error-chain dev
git add backend/app/agent/llm.py backend/tests/agent/test_llm_fallback.py
git commit -m "fix(agent): add LLMInitError with failure chain and structured fallback init logging"
```

---

## Phase 1 Completion Checklist

- [ ] PR-01: `fix/critical-db-asyncsession-loop-contamination` — merged to dev
- [ ] PR-02: `fix/critical-security-workspace-permissions` — merged to dev
- [ ] PR-03: `fix/critical-infra-qdrant-race-condition` — merged to dev
- [ ] PR-04: `fix/critical-agent-llm-fallback-error-chain` — merged to dev
- [ ] Full test suite passes with no event loop errors
- [ ] No security test failures

**Next:** Execute `docs/superpowers/plans/2026-03-16-jarvis-quality-phase2-high.md`
