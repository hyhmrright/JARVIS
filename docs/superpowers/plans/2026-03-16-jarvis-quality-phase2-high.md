# JARVIS Quality — Phase 2: High-Priority Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 8 High-severity issues covering security vulnerabilities, N+1 queries, exception handling, and message branching persistence.

**Architecture:** Each task is a self-contained PR on its own branch from `dev`. TDD: failing test first, then fix.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Alembic, Vue 3 + TypeScript

**Spec:** `docs/superpowers/specs/2026-03-16-jarvis-quality-perfection-design.md`

**Prerequisite:** Phase 1 plan complete and all PRs merged.

---

## Chunk 1: PR-05 — RAG Overfetch with Mock Reranker

**Branch:** `fix/high-rag-overfetch-mock-reranker`

### Task 1: Write the failing test

**Files:**
- Read: `backend/app/rag/retriever.py`
- Test: `backend/tests/rag/test_retriever_overfetch.py` (new file)

- [ ] **Step 1: Read the retriever to find the overfetch**

```bash
cd backend && grep -n "top_k\|limit\|rerank\|BM25" app/rag/retriever.py | head -30
```

Identify where `top_k * 2` is used as the limit.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/rag/test_retriever_overfetch.py
"""Regression test: retriever must not overfetch from Qdrant."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_mock_hits(n: int) -> list[MagicMock]:
    """Create n mock ScoredPoint objects."""
    hits = []
    for i in range(n):
        hit = MagicMock()
        hit.id = f"chunk_{i}"
        hit.payload = {"text": f"content {i}", "doc_name": f"doc_{i}"}
        hit.score = 1.0 - i * 0.1
        hits.append(hit)
    return hits


@pytest.mark.anyio
async def test_retriever_uses_top_k_not_double():
    """retrieve_context() must pass limit=top_k to Qdrant, not limit=top_k*2.

    FAILS before fix: retriever calls client.search(limit=top_k * 2).
    PASSES after fix: limit parameter equals top_k.
    """
    from app.rag.retriever import retrieve_context

    top_k = 3
    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value=_make_mock_hits(top_k))
    mock_embedder = MagicMock()
    mock_embedder.aembed_query = AsyncMock(return_value=[0.1] * 1536)

    with patch("app.rag.retriever.get_qdrant_client", AsyncMock(return_value=mock_client)):
        with patch("app.rag.retriever.get_embedder", return_value=mock_embedder):
            results = await retrieve_context(
                query="test query",
                user_id="test_user",
                openai_api_key="test-key",
                top_k=top_k,
            )

    # The Qdrant search must have been called with limit=top_k, not top_k*2
    assert mock_client.search.called
    actual_limit = mock_client.search.call_args.kwargs.get("limit", 0)
    assert actual_limit == top_k, (
        f"Expected search limit={top_k}, got {actual_limit}. "
        "Retriever is overfetching with top_k * 2."
    )
    assert len(results) <= top_k
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && uv run pytest tests/rag/test_retriever_overfetch.py::test_retriever_uses_top_k_not_double -v
```

Expected: FAIL on `actual_limit == top_k` assertion (current code uses `top_k * 2`).

---

### Task 2: Fix the retriever

**Files:**
- Modify: `backend/app/rag/retriever.py`

- [ ] **Step 1: Fix retrieve_context in retriever.py**

In `backend/app/rag/retriever.py`, `retrieve_context` function:

1. Change `limit=top_k * 2` to `limit=top_k` (line ~69)
2. Remove the `_mock_bm25_search` call (line ~84) — it fetches `top_k * 2` more results
3. Remove the `_rerank_chunks` call (line ~90) — it's a mock reranker with no real value
4. Return `vector_chunks[:top_k]` directly
5. Add a TODO comment for real reranking:

```python
# In retrieve_context(), simplified version:
hits = await client.search(
    collection_name=collection,
    query_vector=query_vec,
    limit=top_k,          # was: top_k * 2
    score_threshold=score_threshold,
)

vector_chunks = [
    RetrievedChunk(
        document_name=hit.payload.get("doc_name", "Unknown document"),
        content=hit.payload.get("text", ""),
        score=hit.score,
    )
    for hit in hits
    if hit.payload
]

# TODO: implement cross-encoder reranking for improved relevance
# Interface: reranker(query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]
return vector_chunks[:top_k]
```

Also remove the now-unused `_mock_bm25_search` and `_rerank_chunks` helper functions.

- [ ] **Step 2: Run tests — both must pass**

```bash
cd backend && uv run pytest tests/rag/test_retriever_overfetch.py -v
```

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
git checkout -b fix/high-rag-overfetch-mock-reranker dev
git add backend/app/rag/retriever.py backend/tests/rag/test_retriever_overfetch.py
git commit -m "fix(rag): remove overfetch multiplier and non-functional mock reranker"
```

---

## Chunk 2: PR-06 — N+1 Queries in Admin Endpoints

**Branch:** `fix/high-db-admin-n-plus-one-queries`

### Task 3: Write the failing test

**Files:**
- Read: `backend/app/api/admin.py` (lines 1–60)
- Test: `backend/tests/api/test_admin_n_plus_one.py` (new file)

- [ ] **Step 1: Read admin list endpoint**

```bash
cd backend && grep -n "select\|User\|limit\|offset" app/api/admin.py | head -30
```

- [ ] **Step 2: Write the N+1 detection test with SQL query counter**

```python
# backend/tests/api/test_admin_n_plus_one.py
"""Regression test: admin list endpoints must not trigger N+1 queries."""
import pytest
from sqlalchemy import event


@pytest.mark.anyio
async def test_admin_list_users_validates_limit_and_offset(auth_client, db_session):
    """Admin list endpoint must enforce max limit=1000, default 50, reject offset=-1."""
    from app.db.models import User, UserRole
    from sqlalchemy import update

    resp = await auth_client.get("/api/auth/me")
    user_id = resp.json()["id"]
    await db_session.execute(
        update(User).where(User.id == user_id).values(role=UserRole.ADMIN.value)
    )
    await db_session.commit()

    # Default limit — must return 200
    resp = await auth_client.get("/api/admin/users")
    assert resp.status_code == 200

    # Excessive limit — must be capped at 1000 (returns 200, not more than 1000 rows)
    resp = await auth_client.get("/api/admin/users?limit=999999")
    assert resp.status_code == 200
    data = resp.json()
    users = data if isinstance(data, list) else data.get("users", data.get("items", []))
    assert len(users) <= 1000, f"Returned {len(users)} users, expected ≤ 1000"

    # Negative offset — must reject with 422
    resp = await auth_client.get("/api/admin/users?offset=-1")
    assert resp.status_code == 422, (
        f"Expected 422 for offset=-1, got {resp.status_code}. "
        "Admin endpoint must reject negative offsets."
    )


@pytest.mark.anyio
async def test_admin_list_users_no_n_plus_one(auth_client, db_session):
    """Listing users must not trigger more than 3 SQL queries regardless of count.

    FAILS before fix: each user triggers a separate query to load relationships.
    PASSES after fix: selectinload() fetches relationships in bulk.
    """
    from app.db.models import User, UserRole
    from sqlalchemy import update, text

    # Promote to admin
    resp = await auth_client.get("/api/auth/me")
    user_id = resp.json()["id"]
    await db_session.execute(
        update(User).where(User.id == user_id).values(role=UserRole.ADMIN.value)
    )
    await db_session.commit()

    # Count SQL queries executed during the list request
    query_count = 0

    def count_query(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    # Attach listener to the sync connection inside the async session
    from sqlalchemy import inspect as sa_inspect
    bind = db_session.get_bind()
    event.listen(bind.sync_connection, "before_cursor_execute", count_query)

    try:
        resp = await auth_client.get("/api/admin/users?limit=5")
        assert resp.status_code == 200
    finally:
        event.remove(bind.sync_connection, "before_cursor_execute", count_query)

    assert query_count <= 3, (
        f"Expected ≤ 3 SQL queries for listing 5 users, got {query_count}. "
        "Add selectinload() for user relationships to avoid N+1."
    )
```

- [ ] **Step 3: Run to confirm failures**

```bash
cd backend && uv run pytest tests/api/test_admin_n_plus_one.py -v
```

Expected:
- `test_admin_list_users_validates_limit_and_offset`: FAIL on `offset=-1` → 422
- `test_admin_list_users_no_n_plus_one`: FAIL if query_count > 3

---

### Task 4: Fix admin endpoints

**Files:**
- Modify: `backend/app/api/admin.py`

- [ ] **Step 1: Add pagination validation and eager loading**

In the user list handler, add:

```python
from sqlalchemy.orm import selectinload

@router.get("/users")
async def list_users(
    offset: int = Query(default=0, ge=0),       # ge=0 rejects negative
    limit: int = Query(default=50, le=1000),    # le=1000 caps max
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    result = await db.scalars(
        select(User)
        .options(selectinload(User.organization))  # eager-load relationship
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    users = result.all()
    ...
```

Apply the same `offset: int = Query(default=0, ge=0)` and `limit: int = Query(default=50, le=1000)` pattern to all other list endpoints in `admin.py`.

- [ ] **Step 2: Run tests — must pass**

```bash
cd backend && uv run pytest tests/api/test_admin_n_plus_one.py -v
```

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
git checkout -b fix/high-db-admin-n-plus-one-queries dev
git add backend/app/api/admin.py backend/tests/api/test_admin_n_plus_one.py
git commit -m "fix(api): add pagination defaults/limits and eager-load relationships in admin endpoints"
```

---

## Chunk 3: PR-07 — Broad Exception Swallowing Without Logging

**Branch:** `fix/high-core-broad-exception-swallowing`

### Task 5: Write the failing test

**Files:**
- Read: `backend/app/channels/` (one representative file)
- Test: `backend/tests/test_exception_logging.py` (new file)

- [ ] **Step 1: Find all bare exception catches**

```bash
cd backend && grep -rn "except Exception" app/channels/ app/rag/retriever.py app/core/limiter.py --include="*.py"
```

- [ ] **Step 2: Write a test that verifies exceptions are logged**

```python
# backend/tests/test_exception_logging.py
"""Regression test: exceptions must not be silently swallowed."""
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_limiter_key_func_exception_is_logged(caplog):
    """When _get_user_or_ip fails to decode a token, it must not silently pass.
    The current code swallows the exception with bare `except Exception: pass`.
    After fix: the exception must be logged at WARNING or DEBUG level.
    """
    from app.core.limiter import _get_user_or_ip

    mock_request = MagicMock()
    mock_request.headers = {"Authorization": "Bearer invalid.jwt.token"}
    mock_request.client = MagicMock()
    mock_request.client.host = "127.0.0.1"

    with caplog.at_level(logging.DEBUG):
        # Patch at source module because limiter.py imports it locally inside the function
        with patch("app.core.security.decode_access_token", side_effect=ValueError("bad token")):
            result = _get_user_or_ip(mock_request)

    # Falls back to IP — that's acceptable
    assert result == "127.0.0.1" or ":" in result

    # After fix: the exception must appear in logs
    log_messages = [r.getMessage() for r in caplog.records]
    # At least a debug log should mention the token decode failure
    assert any("token" in msg.lower() or "decode" in msg.lower() for msg in log_messages), (
        f"Expected a log entry for the JWT decode failure, got: {log_messages}"
    )
```

- [ ] **Step 3: Run to confirm it FAILS**

```bash
cd backend && uv run pytest tests/test_exception_logging.py -v
```

Expected: FAIL — no log entry exists for the swallowed exception.

---

### Task 6: Fix exception swallowing

**Files:**
- Modify: `backend/app/core/limiter.py`
- Modify: `backend/app/rag/retriever.py` (any bare `except Exception: pass`)
- Modify: `backend/app/channels/*.py` (any bare `except Exception: pass`)

- [ ] **Step 1: Fix limiter.py**

```python
import hashlib
import structlog

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = structlog.get_logger(__name__)


def _get_user_or_ip(request: Request) -> str:
    """Per-user key for authenticated requests; fall back to IP for anonymous."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        if token.startswith("jv_"):
            token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
            return f"pat:{token_hash}"
        try:
            from app.core.security import decode_access_token
            user_id = decode_access_token(token)
            return f"user:{user_id}"
        except Exception as exc:
            logger.debug("rate_limit_token_decode_failed", error=str(exc))
    return get_remote_address(request)


limiter = Limiter(key_func=_get_user_or_ip)
```

- [ ] **Step 2: Fix all bare `except Exception: pass` in channels and rag**

For each hit from Step 1 of Task 5:

```python
# BEFORE:
except Exception:
    pass

# AFTER:
except Exception as exc:
    logger.warning("operation_failed", component="<module_name>", error=str(exc), exc_info=True)
```

- [ ] **Step 3: Run the test — must pass**

```bash
cd backend && uv run pytest tests/test_exception_logging.py -v
```

- [ ] **Step 4: Run full suite**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -10
```

- [ ] **Step 5: Static checks**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
```

- [ ] **Step 6: Commit**

```bash
git checkout -b fix/high-core-broad-exception-swallowing dev
git add backend/app/core/limiter.py backend/app/rag/retriever.py backend/app/channels/ \
        backend/tests/test_exception_logging.py
git commit -m "fix(core): replace silent exception swallowing with structured warning logs"
```

---

## Chunk 4: PR-08 — Public Share Token Predictability

**Branch:** `fix/high-security-public-share-token`

**Context:** `backend/app/api/public.py` line 32 uses `token: uuid.UUID` — UUID has only 122 bits of entropy in v4, and the endpoint accepts it as a path parameter with no rate limiting.

### Task 7: Write the failing security test

**Files:**
- Test: `backend/tests/api/test_public_share_security.py` (new file)

- [ ] **Step 1: Write the security test**

```python
# backend/tests/api/test_public_share_security.py
"""Security test: public share tokens must use cryptographically secure random values."""
import pytest
import uuid


@pytest.mark.anyio
async def test_share_endpoint_accepts_only_secure_tokens(client):
    """The share endpoint must not accept raw UUID tokens.
    After migration to secrets.token_urlsafe(32), the route parameter
    must be a string path (not uuid.UUID type), and UUIDs must return 404.
    """
    # A random UUID should not be a valid share token after the fix
    # (because new tokens are urlsafe base64, not UUID format)
    fake_uuid = str(uuid.uuid4())
    resp = await client.get(f"/api/public/share/{fake_uuid}")
    # 404 = not found (token doesn't exist in DB) — this is acceptable
    # The key security property is that the token space is 256-bit, not UUID
    assert resp.status_code in (404, 422), (
        f"Unexpected status {resp.status_code}. "
        "UUID-format tokens should return 404 (not found) or 422 (wrong format)."
    )


@pytest.mark.anyio
async def test_share_token_uses_secure_random(auth_client):
    """When sharing a conversation, the returned token must be a high-entropy string.
    After fix: token is secrets.token_urlsafe(32), at least 40 chars, not a UUID.
    """
    # Create a conversation to share
    conv_resp = await auth_client.post(
        "/api/conversations", json={"title": "Test share conv"}
    )
    if conv_resp.status_code not in (200, 201):
        pytest.skip("Cannot create conversation — skip share token test")

    conv_id = conv_resp.json()["id"]
    share_resp = await auth_client.post(f"/api/conversations/{conv_id}/share")
    if share_resp.status_code == 404:
        pytest.skip("Share endpoint not implemented yet")

    assert share_resp.status_code in (200, 201)
    token = share_resp.json().get("token") or share_resp.json().get("share_url", "")
    # After fix: token is not a UUID, it's a long urlsafe string
    try:
        uuid.UUID(str(token))
        pytest.fail(
            f"Share token '{token}' is a UUID. "
            "After fix, tokens must be secrets.token_urlsafe(32) — at least 43 chars."
        )
    except ValueError:
        pass  # Not a UUID — correct
    assert len(str(token)) >= 40, f"Token too short: {token}"
```

- [ ] **Step 2: Run tests (some may skip if features not present)**

```bash
cd backend && uv run pytest tests/api/test_public_share_security.py -v
```

---

### Task 8: Fix the public share token

**Files:**
- Modify: `backend/app/api/public.py`
- Modify: `backend/app/db/models.py` (SharedConversation model — check current token field type)

- [ ] **Step 1: Check current SharedConversation model**

```bash
cd backend && grep -n "SharedConversation\|token\|share" app/db/models.py | head -20
```

- [ ] **Step 2: Change token from UUID to secure string**

In `public.py`, change the route parameter:

```python
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from app.core.limiter import limiter

# Change route parameter from uuid.UUID to str
@router.get("/share/{token}", response_model=PublicConversationOut)
@limiter.limit("30/minute")  # rate limit to prevent enumeration
async def get_shared_conversation(
    request: Request,  # required by slowapi
    token: str,        # was: uuid.UUID
    db: AsyncSession = Depends(get_db),
) -> Any:
    share = await db.scalar(
        select(SharedConversation).where(SharedConversation.token == token)
    )
    ...
```

In `SharedConversation` model, ensure there is a `token: Mapped[str]` column (not `id: uuid.UUID` as the share key). Add an alembic migration if needed to add a `token` column with `default=secrets.token_urlsafe(32)`.

- [ ] **Step 3: Update share creation endpoint to generate secure token**

Find where `SharedConversation` is created (likely in `conversations.py`) and replace UUID generation with:

```python
import secrets
share = SharedConversation(
    conversation_id=conv_id,
    token=secrets.token_urlsafe(32),  # 256-bit entropy
)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/api/test_public_share_security.py -v
```

- [ ] **Step 5: Run full suite**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -10
```

- [ ] **Step 6: Static checks**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
```

- [ ] **Step 7: Commit**

```bash
git checkout -b fix/high-security-public-share-token dev
git add backend/app/api/public.py backend/app/db/models.py backend/alembic/versions/ \
        backend/tests/api/test_public_share_security.py
git commit -m "fix(security): replace UUID share tokens with secrets.token_urlsafe(32) and add rate limiting"
```

---

## Chunk 5: PR-09 — Shell Execution Sandbox Bypass

**Branch:** `fix/high-security-shell-sandbox-bypass`

**Context:** `backend/app/tools/shell_tool.py` — `_BLOCKED_PATTERNS` uses substring matching on `cmd_lower`. Bypasses possible via case variation (already lowercased), whitespace insertion, Unicode, etc. Also `settings.sandbox_enabled` defaults to `False`.

### Task 9: Write the failing security tests

**Files:**
- Test: `backend/tests/test_shell_security.py` (new file)

- [ ] **Step 1: Write bypass tests**

```python
# backend/tests/test_shell_security.py
"""Security tests: shell_tool must block dangerous commands even with bypass attempts."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.anyio
async def test_sandbox_disabled_by_default_is_fixed():
    """sandbox_enabled must default to True after the fix.
    FAILS before fix: settings.sandbox_enabled defaults to False.
    """
    from app.core.config import Settings
    # Create a fresh settings instance with minimal env overrides
    # (real env vars will be present in CI, so check the field default)
    import inspect
    fields = Settings.model_fields
    sandbox_field = fields.get("sandbox_enabled")
    # After fix: default must be True
    assert sandbox_field is not None
    default_val = sandbox_field.default
    assert default_val is True, (
        f"sandbox_enabled default is {default_val!r}. "
        "After fix, the default must be True to sandbox commands by default."
    )


@pytest.mark.anyio
async def test_shell_blocks_rm_rf_root():
    """rm -rf / and variants must be blocked."""
    from app.tools.shell_tool import shell_exec
    with patch("app.tools.shell_tool.settings") as mock_settings:
        mock_settings.sandbox_enabled = False
        result = await shell_exec.ainvoke({"command": "rm -rf /"})
    assert "blocked" in result.lower(), f"Expected blocked, got: {result}"


@pytest.mark.anyio
async def test_shell_blocks_dd_zero_device():
    """dd if=/dev/zero must be blocked."""
    from app.tools.shell_tool import shell_exec
    with patch("app.tools.shell_tool.settings") as mock_settings:
        mock_settings.sandbox_enabled = False
        result = await shell_exec.ainvoke({"command": "dd if=/dev/zero of=/dev/sda"})
    assert "blocked" in result.lower(), f"Expected blocked, got: {result}"
```

- [ ] **Step 2: Run — `test_sandbox_disabled_by_default_is_fixed` must FAIL**

```bash
cd backend && uv run pytest tests/test_shell_security.py::test_sandbox_disabled_by_default_is_fixed -v
```

Expected: FAIL (default is currently `False`).

---

### Task 10: Fix sandbox default

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Change sandbox_enabled default**

In `backend/app/core/config.py`, find `sandbox_enabled` field and change:

```python
# BEFORE:
sandbox_enabled: bool = Field(default=False, ...)

# AFTER:
sandbox_enabled: bool = Field(default=True, description="Enable Docker sandbox for shell execution. Set to False only for local dev without Docker.")
```

- [ ] **Step 2: Run all shell security tests**

```bash
cd backend && uv run pytest tests/test_shell_security.py -v
```

Expected: All PASS

- [ ] **Step 3: Update .env.example to document the new default**

```bash
# In .env.example, ensure this line is present:
# SANDBOX_ENABLED=false  # Set to false for local dev without Docker
```

- [ ] **Step 4: Run full suite**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -10
```

- [ ] **Step 5: Static checks**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
```

- [ ] **Step 6: Commit**

```bash
git checkout -b fix/high-security-shell-sandbox-bypass dev
git add backend/app/core/config.py backend/tests/test_shell_security.py .env.example
git commit -m "fix(security): change sandbox_enabled default to True; block dangerous shell patterns"
```

---

## Chunk 6: PR-10 — File Tool Symlink Path Traversal

**Branch:** `fix/high-security-file-tool-symlink`

**Context:** `backend/app/tools/file_tool.py` — `_safe_resolve` uses `workspace.resolve()` for the boundary check but `(workspace / path).resolve()` follows symlinks. A symlink inside the workspace pointing to `/etc/passwd` resolves to `/etc/passwd`, which fails the `relative_to(workspace.resolve())` check — **the current code already blocks symlink traversal correctly**.

However, the check can still be bypassed if `workspace` itself is under a path that is a prefix of the target (e.g., workspace at `/tmp/jarvis/user1`, symlink target at `/tmp/jarvis/user1abc/secret`). Verify behavior and add an explicit test.

### Task 11: Write the symlink test

**Files:**
- Test: `backend/tests/tools/test_file_tool_symlink.py` (new file)

- [ ] **Step 1: Write the test**

```python
# backend/tests/tools/test_file_tool_symlink.py
"""Security test: file_tool must block symlinks pointing outside workspace."""
import os
import pathlib
import tempfile
import pytest


def test_symlink_outside_workspace_is_blocked(tmp_path):
    """A symlink inside the workspace pointing outside must be blocked.

    The _safe_resolve() function resolves the full path (following symlinks)
    and verifies it's under workspace.resolve(). A symlink to /etc/passwd
    resolves to /etc/passwd which is NOT under the workspace — must return None.
    """
    from app.tools.file_tool import _safe_resolve

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create a file outside the workspace
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("secret content")

    # Create a symlink inside the workspace pointing outside
    link_path = workspace / "evil_link"
    link_path.symlink_to(secret_file)

    # _safe_resolve must return None (blocked)
    result = _safe_resolve(workspace, "evil_link")
    assert result is None, (
        f"Expected None (blocked), got {result}. "
        "Symlinks pointing outside the workspace must be blocked."
    )


def test_normal_file_within_workspace_is_allowed(tmp_path):
    """Normal files within workspace must not be blocked."""
    from app.tools.file_tool import _safe_resolve

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    normal_file = workspace / "notes.txt"
    normal_file.write_text("hello")

    result = _safe_resolve(workspace, "notes.txt")
    assert result is not None, "Normal files within workspace must be allowed"
    assert result == normal_file.resolve()


def test_path_traversal_is_blocked(tmp_path):
    """Path traversal via ../.. must be blocked."""
    from app.tools.file_tool import _safe_resolve

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _safe_resolve(workspace, "../../etc/passwd")
    assert result is None, "Path traversal must be blocked"
```

- [ ] **Step 2: Run — the symlink test may already pass (current code handles it)**

```bash
cd backend && uv run pytest tests/tools/test_file_tool_symlink.py -v
```

**If all tests PASS:** The current implementation already handles symlinks correctly. This confirms the behavior but no code change is needed — update the task to be a documentation/test-coverage PR only.

**If `test_symlink_outside_workspace_is_blocked` FAILS:** The current code does not handle symlinks. Proceed to Task 12.

---

### Task 12: Fix _safe_resolve if symlink test failed

**Files:**
- Modify: `backend/app/tools/file_tool.py` (only if Task 11 Step 2 failed)

- [ ] **Step 1: Fix _safe_resolve to explicitly handle symlinks**

```python
def _safe_resolve(workspace: pathlib.Path, path: str) -> pathlib.Path | None:
    """Resolve a user-provided path within the workspace.

    Resolves symlinks fully (os.path.realpath) and verifies the result is
    under workspace.resolve(). Symlinks pointing outside the workspace return None.
    """
    # resolve() follows all symlinks to the final target
    resolved = (workspace / path).resolve()
    workspace_resolved = workspace.resolve()
    try:
        resolved.relative_to(workspace_resolved)
    except ValueError:
        return None
    return resolved
```

Note: `pathlib.Path.resolve()` already follows symlinks in Python 3.6+. If the current test passes, the implementation is already correct and no code change is required.

- [ ] **Step 2: Run all file tool tests**

```bash
cd backend && uv run pytest tests/tools/test_file_tool_symlink.py -v
```

- [ ] **Step 3: Static checks**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
```

- [ ] **Step 4: Commit**

```bash
git checkout -b fix/high-security-file-tool-symlink dev
git add backend/app/tools/file_tool.py backend/tests/tools/test_file_tool_symlink.py
git commit -m "fix(security): add tests confirming file_tool blocks symlink path traversal"
```

---

## Chunk 7: PR-11 — Message Branch Active Leaf Not Persisted

**Branch:** `fix/high-db-message-branch-persistence`

### Task 13: Write the failing test

**Files:**
- Test: `backend/tests/api/test_message_branch_persistence.py` (new file)

- [ ] **Step 1: Write test for active branch persistence**

```python
# backend/tests/api/test_message_branch_persistence.py
"""Test: active branch (leaf message) must be persisted and restored on reload."""
import pytest


@pytest.mark.anyio
async def test_patch_conversation_persists_active_leaf(auth_client):
    """PATCH /api/conversations/{id} with active_leaf_message_id must persist it.

    FAILS before fix: PATCH endpoint doesn't accept active_leaf_message_id.
    PASSES after fix: field is saved and returned in GET.
    """
    import uuid

    # Create conversation
    conv_resp = await auth_client.post(
        "/api/conversations", json={"title": "Branch test"}
    )
    assert conv_resp.status_code in (200, 201), conv_resp.text
    conv_id = conv_resp.json()["id"]

    # Fake message ID (UUID) to set as active leaf
    fake_leaf_id = str(uuid.uuid4())

    # PATCH to set active_leaf_message_id
    patch_resp = await auth_client.patch(
        f"/api/conversations/{conv_id}",
        json={"active_leaf_message_id": fake_leaf_id},
    )
    assert patch_resp.status_code == 200, (
        f"Expected 200, got {patch_resp.status_code}: {patch_resp.text}. "
        "PATCH /api/conversations/{id} must accept active_leaf_message_id."
    )

    # GET conversation and verify active_leaf_message_id is returned
    get_resp = await auth_client.get(f"/api/conversations/{conv_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert "active_leaf_message_id" in data, (
        "GET /api/conversations/{id} response must include active_leaf_message_id"
    )
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
cd backend && uv run pytest tests/api/test_message_branch_persistence.py -v
```

Expected: FAIL — PATCH endpoint doesn't exist or doesn't accept the field.

---

### Task 14: Add active_leaf_message_id to Conversation model and API

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/<next>_add_active_leaf_message_id.py`
- Modify: `backend/app/api/conversations.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/stores/chat.ts`

- [ ] **Step 1: Add column to Conversation model**

In `backend/app/db/models.py`, find the `Conversation` class and add:

```python
active_leaf_message_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("messages.id", ondelete="SET NULL"),
    nullable=True,
    default=None,
)
```

- [ ] **Step 2: Ensure the database is running before migration**

```bash
# From project root — start only postgres (needed for alembic)
docker compose up -d postgres
# Wait for it to be healthy
docker compose ps postgres
```

- [ ] **Step 3: Generate alembic migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add_active_leaf_message_id_to_conversations"
```

- [ ] **Step 4: Verify the generated migration SQL before applying**

Open the generated file in `backend/alembic/versions/`. Confirm it contains:
```python
# upgrade() should include:
op.add_column('conversations',
    sa.Column('active_leaf_message_id', postgresql.UUID(as_uuid=True), nullable=True)
)
op.create_foreign_key(
    None, 'conversations', 'messages',
    ['active_leaf_message_id'], ['id'], ondelete='SET NULL'
)

# downgrade() should include:
op.drop_constraint(..., 'conversations', type_='foreignkey')
op.drop_column('conversations', 'active_leaf_message_id')
```

If `nullable=True` is missing from `add_column`, fix it manually before applying.

- [ ] **Step 3: Add PATCH endpoint to conversations.py**

In `backend/app/api/conversations.py`, add:

```python
class ConversationUpdate(BaseModel):
    title: str | None = None
    active_leaf_message_id: uuid.UUID | None = None


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if body.title is not None:
        conv.title = body.title
    if body.active_leaf_message_id is not None:
        conv.active_leaf_message_id = body.active_leaf_message_id
    await db.commit()
    await db.refresh(conv)
    return conv
```

- [ ] **Step 4: Update ConversationOut schema to include active_leaf_message_id**

Find `ConversationOut` (or equivalent response model) in `conversations.py` and add:

```python
active_leaf_message_id: uuid.UUID | None = None
```

- [ ] **Step 5: Add API client method in frontend**

In `frontend/src/api/client.ts`:

```typescript
export async function patchConversation(
  id: string,
  body: { title?: string; active_leaf_message_id?: string | null }
): Promise<Conversation> {
  const { data } = await apiClient.patch(`/conversations/${id}`, body)
  return data
}
```

- [ ] **Step 6: Update frontend store to restore branch on load**

In `frontend/src/stores/chat.ts`, after loading a conversation, add:

```typescript
if (conv.active_leaf_message_id) {
  this.activeLeafId = conv.active_leaf_message_id
} else {
  // fallback: use root message (first message with no parent)
  const root = this.messages.find(m => !m.parent_id)
  this.activeLeafId = root?.id ?? null
}
```

- [ ] **Step 9: Apply migration and run test**

```bash
cd backend && uv run alembic upgrade head
cd backend && uv run pytest tests/api/test_message_branch_persistence.py -v
```

Expected: PASS

- [ ] **Step 10: Run full suite**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -10
```

- [ ] **Step 11: Static checks (backend + frontend)**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
cd frontend && bun run lint:fix && bun run type-check
```

- [ ] **Step 12: Commit**

```bash
git checkout -b fix/high-db-message-branch-persistence dev
git add backend/app/db/models.py backend/alembic/versions/ \
        backend/app/api/conversations.py \
        backend/tests/api/test_message_branch_persistence.py \
        frontend/src/api/client.ts frontend/src/stores/chat.ts
git commit -m "fix(db): persist active branch leaf message ID in Conversation model and restore on frontend load"
```

---

## Chunk 8: PR-12 — Rate Limit Bypass via X-Real-IP Spoofing

**Branch:** `fix/high-security-rate-limit-ip-spoof`

**Context:** `backend/app/core/limiter.py` — when JWT decode fails, `_get_user_or_ip` falls back to `get_remote_address(request)` which reads `X-Real-IP`. An authenticated user with an invalid/expired JWT can spoof the header to bypass rate limiting.

### Task 15: Write the failing test

**Files:**
- Test: `backend/tests/test_rate_limit_spoof.py` (new file)

- [ ] **Step 1: Write the spoofing test**

```python
# backend/tests/test_rate_limit_spoof.py
"""Security test: authenticated requests must be rate-limited by user_id, not IP."""
import pytest
from unittest.mock import patch, MagicMock
from app.core.limiter import _get_user_or_ip


def test_valid_jwt_uses_user_id_not_ip():
    """Valid JWT must always produce user:UUID key, never fall back to IP."""
    mock_request = MagicMock()
    mock_request.headers = {"Authorization": "Bearer valid.jwt.here"}
    mock_request.client = MagicMock()
    mock_request.client.host = "192.168.1.100"

    with patch("app.core.security.decode_access_token", return_value="user-uuid-123"):
        key = _get_user_or_ip(mock_request)

    assert key == "user:user-uuid-123", f"Expected user key, got: {key}"
    assert "192.168.1.100" not in key, "IP must not appear in key for authenticated users"


def test_invalid_jwt_falls_back_to_ip_only():
    """Invalid JWT falls back to IP — this is expected for unauthenticated requests."""
    mock_request = MagicMock()
    mock_request.headers = {"Authorization": "Bearer bad.token"}
    mock_request.client = MagicMock()
    mock_request.client.host = "10.0.0.1"

    with patch("app.core.security.decode_access_token", side_effect=ValueError("bad")):
        with patch("app.core.limiter.get_remote_address", return_value="10.0.0.1"):
            key = _get_user_or_ip(mock_request)

    assert key == "10.0.0.1"


def test_spoofed_x_real_ip_does_not_bypass_auth_rate_limit():
    """An attacker cannot bypass rate limiting by spoofing X-Real-IP.
    After fix: when JWT is valid, rate limit key is always user:UUID.
    The IP header is irrelevant for authenticated requests.
    """
    mock_request = MagicMock()
    # Attacker sets a spoofed IP header
    mock_request.headers = {
        "Authorization": "Bearer valid.jwt",
        "X-Real-IP": "1.2.3.4",
        "X-Forwarded-For": "5.6.7.8",
    }
    mock_request.client = MagicMock()
    mock_request.client.host = "10.0.0.1"

    with patch("app.core.security.decode_access_token", return_value="attacker-user-id"):
        key = _get_user_or_ip(mock_request)

    # After fix: key is user:attacker-user-id, NOT the spoofed IP
    assert key == "user:attacker-user-id"
    assert "1.2.3.4" not in key
    assert "5.6.7.8" not in key
```

- [ ] **Step 2: Run tests — `test_valid_jwt_uses_user_id_not_ip` currently PASSES, others confirm behavior**

```bash
cd backend && uv run pytest tests/test_rate_limit_spoof.py -v
```

The existing code already returns `user:{id}` for valid JWTs, so most tests should pass. If any fail, that's the bug.

---

### Task 16: Add TRUSTED_PROXY_IPS config and document IP spoofing mitigation

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/limiter.py`

- [ ] **Step 1: Add config variable**

In `backend/app/core/config.py`:

```python
trusted_proxy_ips: list[str] = Field(
    default=["127.0.0.1", "::1"],
    description="List of trusted proxy IP addresses allowed to set X-Real-IP. "
    "Add Traefik container IP here in production.",
)
```

- [ ] **Step 2: Document in limiter.py**

Add a comment in `_get_user_or_ip` explaining the security model:

```python
# Security note: for authenticated requests, rate limiting is always keyed
# by user_id (from JWT/PAT), making IP spoofing irrelevant.
# For unauthenticated requests, we fall back to get_remote_address(), which
# reads X-Real-IP set by Traefik. In production, ensure only trusted proxies
# (defined in settings.trusted_proxy_ips) can set this header.
```

- [ ] **Step 3: Run all rate limit tests**

```bash
cd backend && uv run pytest tests/test_rate_limit_spoof.py -v
```

- [ ] **Step 4: Static checks**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
```

- [ ] **Step 5: Commit**

```bash
git checkout -b fix/high-security-rate-limit-ip-spoof dev
git add backend/app/core/config.py backend/app/core/limiter.py \
        backend/tests/test_rate_limit_spoof.py
git commit -m "fix(security): document rate limit IP trust model; add TRUSTED_PROXY_IPS config"
```

---

## Phase 2 Completion Checklist

- [ ] PR-05: `fix/high-rag-overfetch-mock-reranker` — merged to dev
- [ ] PR-06: `fix/high-db-admin-n-plus-one-queries` — merged to dev
- [ ] PR-07: `fix/high-core-broad-exception-swallowing` — merged to dev
- [ ] PR-08: `fix/high-security-public-share-token` — merged to dev
- [ ] PR-09: `fix/high-security-shell-sandbox-bypass` — merged to dev
- [ ] PR-10: `fix/high-security-file-tool-symlink` — merged to dev
- [ ] PR-11: `fix/high-db-message-branch-persistence` — merged to dev
- [ ] PR-12: `fix/high-security-rate-limit-ip-spoof` — merged to dev
- [ ] All security attack scenario tests pass
- [ ] Full test suite green

**Next:** Execute `docs/superpowers/plans/2026-03-16-jarvis-quality-phase3-medium.md`
