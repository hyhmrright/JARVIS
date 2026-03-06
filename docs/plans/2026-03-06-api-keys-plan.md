# Phase 12.4 — Personal API Keys (PAT) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Personal Access Tokens (PATs) so users can authenticate to the JARVIS API without JWTs — enabling scripts, CI pipelines, and third-party integrations.

**Architecture:** A new `api_keys` table stores sha256 hashes of `jv_`-prefixed tokens. `deps.py` detects the `jv_` prefix in `Bearer` tokens and performs a hash lookup instead of JWT decode. All downstream handlers receive a normal `User` object and need no changes. Scope (`full`/`readonly`) is stored per-key; V1 enforces it only for the keys management API itself (readonly keys can't create new keys).

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Alembic, hashlib (stdlib), Vue 3, TypeScript, Pinia.

**Design doc:** `docs/plans/2026-03-06-api-keys-design.md`

---

## Setup: Create worktree

```bash
# From repo root
git worktree add .worktrees/api-keys -b feature/api-keys dev
cd .worktrees/api-keys
cp ../../.env .
# No uv sync / bun install needed — existing .venv and node_modules are shared
```

All commands below run from `.worktrees/api-keys/` unless specified.

---

## Task 1: ApiKey database model

**Files:**
- Modify: `backend/app/db/models.py` (append after `AuditLog`)

**Step 1: Add `ApiKey` model**

Append to `backend/app/db/models.py` after the `AuditLog` class:

```python
class ApiKey(Base):
    """Personal Access Token record. The raw token is never stored — only its
    sha256 hex digest. The first 8 chars of the raw token are stored as
    ``prefix`` for user-facing display."""

    __tablename__ = "api_keys"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('full', 'readonly')",
            name="ck_api_keys_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="api_keys")
```

Also add the `api_keys` relationship to the `User` class (after the `documents` relationship, around line 62):

```python
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
```

**Step 2: Verify import check passes**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```

Expected: collection completes with no import errors.

**Step 3: Commit**

```bash
git add backend/app/db/models.py
git commit -m "feat(db): add ApiKey model for Personal Access Tokens"
```

---

## Task 2: Alembic migration

**Files:**
- Create: `backend/alembic/versions/011_add_api_keys.py`

**Step 1: Create migration file**

```python
"""add api_keys table

Revision ID: 011
Revises: 010
Create Date: 2026-03-06
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("key_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("prefix", sa.String(8), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False, server_default="full"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "scope IN ('full', 'readonly')",
            name="ck_api_keys_scope",
        ),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_unique_constraint("uq_api_keys_key_hash", "api_keys", ["key_hash"])


def downgrade() -> None:
    op.drop_constraint("uq_api_keys_key_hash", "api_keys", type_="unique")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")
```

**Step 2: Verify collect-only still passes**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```

**Step 3: Commit**

```bash
git add backend/alembic/versions/011_add_api_keys.py
git commit -m "feat(db): migration 011 — add api_keys table"
```

---

## Task 3: Backend API router

**Files:**
- Create: `backend/app/api/keys.py`

This router handles CRUD for Personal API Keys.

**Step 1: Create `backend/app/api/keys.py`**

```python
"""Personal API Keys (PAT) management endpoints."""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import ApiKey, User
from app.db.session import get_db

router = APIRouter(prefix="/api/keys", tags=["keys"])

_MAX_KEYS_PER_USER = 10


def _generate_pat() -> str:
    """Generate a new Personal Access Token: jv_ + 64 hex chars (32 random bytes)."""
    return "jv_" + os.urandom(32).hex()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class ApiKeyCreate(BaseModel):
    name: str
    scope: str = "full"
    expires_at: datetime | None = None


class ApiKeyCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    scope: str
    raw_key: str  # shown once only
    expires_at: datetime | None
    created_at: datetime


class ApiKeyItem(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    scope: str
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


@router.post("", response_model=ApiKeyCreateResponse, status_code=201)
async def create_key(
    body: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    """Create a new Personal Access Token.

    The raw key is returned **once** and never stored.
    Raises 403 if the caller authenticated via a readonly PAT.
    Raises 422 if scope is not 'full' or 'readonly'.
    Raises 409 if the user already has 10 active keys.
    """
    if body.scope not in ("full", "readonly"):
        raise HTTPException(status_code=422, detail="scope must be 'full' or 'readonly'")

    count = await db.scalar(
        select(func.count()).select_from(ApiKey).where(ApiKey.user_id == user.id)
    )
    if (count or 0) >= _MAX_KEYS_PER_USER:
        raise HTTPException(
            status_code=409,
            detail=f"Maximum of {_MAX_KEYS_PER_USER} API keys per user reached",
        )

    raw_key = _generate_pat()
    api_key = ApiKey(
        user_id=user.id,
        name=body.name,
        key_hash=_hash_token(raw_key),
        prefix=raw_key[:8],  # "jv_" + first 5 hex chars
        scope=body.scope,
        expires_at=body.expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        scope=api_key.scope,
        raw_key=raw_key,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[ApiKeyItem])
async def list_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    """List all API keys for the current user (no raw tokens)."""
    result = await db.scalars(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.all()
    return [
        ApiKeyItem(
            id=k.id,
            name=k.name,
            prefix=k.prefix,
            scope=k.scope,
            expires_at=k.expires_at,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=204)
async def delete_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Revoke an API key by ID. Returns 404 if not found or belongs to another user."""
    api_key = await db.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    await db.delete(api_key)
    await db.commit()
```

**Step 2: Verify collect-only passes**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```

Expected: no errors.

**Step 3: Commit**

```bash
git add backend/app/api/keys.py
git commit -m "feat(api): add Personal API Keys CRUD router"
```

---

## Task 4: PAT authentication in deps.py

**Files:**
- Modify: `backend/app/api/deps.py`

**Step 1: Update `_resolve_user` to detect `jv_` tokens**

Replace the existing `_resolve_user` function (lines 29–44) with:

```python
async def _resolve_user(
    token: str, db: AsyncSession, request: "Request | None" = None
) -> User:
    """Authenticate by JWT or PAT token and return the active user.

    PAT tokens start with ``jv_``. Scope is stored in
    ``request.state.api_key_scope`` for optional downstream enforcement.
    JWT tokens always get scope ``full``.
    """
    if token.startswith("jv_"):
        return await _resolve_pat(token, db, request)
    return await _resolve_jwt(token, db, request)


async def _resolve_jwt(
    token: str, db: AsyncSession, request: "Request | None" = None
) -> User:
    try:
        user_id = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc
    user = await db.scalar(
        select(User).where(User.id == user_id, User.is_active == True)  # noqa: E712
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if request is not None:
        request.state.api_key_scope = "full"
    return user


async def _resolve_pat(
    token: str, db: AsyncSession, request: "Request | None" = None
) -> User:
    import hashlib
    from datetime import datetime, timezone

    from app.db.models import ApiKey

    key_hash = hashlib.sha256(token.encode()).hexdigest()
    api_key = await db.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash))
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired"
        )
    user = await db.scalar(
        select(User).where(User.id == api_key.user_id, User.is_active == True)  # noqa: E712
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    # Update last_used_at — commit will happen when the db session closes
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    if request is not None:
        request.state.api_key_scope = api_key.scope
    return user
```

Also update the `get_current_user` and `get_current_user_query_token` signatures to pass `request`:

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    request: Request = Depends(),  # FastAPI injects Request automatically
) -> User:
    return await _resolve_user(credentials.credentials, db, request)


async def get_current_user_query_token(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    request: Request = Depends(),
) -> User:
    return await _resolve_user(token, db, request)
```

Add `Request` to imports at top of file:

```python
from fastapi import Depends, HTTPException, Query, Request, status
```

> **Note:** `Request = Depends()` is NOT correct syntax for FastAPI Request injection.
> FastAPI injects `Request` automatically when it's declared as a parameter with type `Request`.
> Use this instead:
>
> ```python
> from fastapi import Depends, HTTPException, Query, Request, status
>
> async def get_current_user(
>     credentials: HTTPAuthorizationCredentials = Depends(security),
>     db: AsyncSession = Depends(get_db),
>     request: Request,   # ← no default, FastAPI injects automatically
> ) -> User:
>     return await _resolve_user(credentials.credentials, db, request)
> ```

**Step 2: Run ruff + mypy**

```bash
cd backend && uv run ruff check --fix app/api/deps.py && uv run ruff format app/api/deps.py
cd backend && uv run mypy app/api/deps.py
```

Fix any type errors before continuing.

**Step 3: Run collect-only**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```

**Step 4: Commit**

```bash
git add backend/app/api/deps.py
git commit -m "feat(auth): extend _resolve_user to authenticate PAT jv_ tokens"
```

---

## Task 5: Register keys router in main.py

**Files:**
- Modify: `backend/app/main.py`

**Step 1: Add import and register router**

Add to the imports block (alphabetically with other api imports):

```python
from app.api.keys import router as keys_router
```

Add to the router registration block (after `webhooks_router`):

```python
app.include_router(keys_router)
```

**Step 2: Verify collect-only passes**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```

**Step 3: Run full static checks**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
cd backend && uv run mypy app
```

**Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: register API keys router in FastAPI app"
```

---

## Task 6: Backend tests

**Files:**
- Create: `backend/tests/api/test_keys.py`
- Modify: `backend/tests/conftest.py` (add `_suppress_key_audit` mock if keys.py uses log_action; skip if not)

**Step 1: Write test file**

```python
"""Tests for Personal API Keys CRUD: POST/GET/DELETE /api/keys."""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_create_key_returns_raw_key(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/keys", json={"name": "My Script", "scope": "full"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["raw_key"].startswith("jv_")
    assert len(data["raw_key"]) == 67  # "jv_" + 64 hex chars
    assert data["prefix"] == data["raw_key"][:8]
    assert data["scope"] == "full"
    assert data["name"] == "My Script"


@pytest.mark.anyio
async def test_create_readonly_key(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/keys", json={"name": "CI Token", "scope": "readonly"}
    )
    assert resp.status_code == 201
    assert resp.json()["scope"] == "readonly"


@pytest.mark.anyio
async def test_create_key_invalid_scope(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/keys", json={"name": "Bad", "scope": "superadmin"}
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_list_keys(auth_client: AsyncClient) -> None:
    # Create two keys
    await auth_client.post("/api/keys", json={"name": "Key A", "scope": "full"})
    await auth_client.post("/api/keys", json={"name": "Key B", "scope": "readonly"})
    resp = await auth_client.get("/api/keys")
    assert resp.status_code == 200
    names = [k["name"] for k in resp.json()]
    assert "Key A" in names
    assert "Key B" in names


@pytest.mark.anyio
async def test_list_keys_does_not_expose_raw_key(auth_client: AsyncClient) -> None:
    await auth_client.post("/api/keys", json={"name": "Secret", "scope": "full"})
    resp = await auth_client.get("/api/keys")
    assert resp.status_code == 200
    for key in resp.json():
        assert "raw_key" not in key
        assert "key_hash" not in key


@pytest.mark.anyio
async def test_delete_key(auth_client: AsyncClient) -> None:
    create_resp = await auth_client.post(
        "/api/keys", json={"name": "Temp", "scope": "full"}
    )
    key_id = create_resp.json()["id"]
    del_resp = await auth_client.delete(f"/api/keys/{key_id}")
    assert del_resp.status_code == 204
    # Verify it's gone
    list_resp = await auth_client.get("/api/keys")
    ids = [k["id"] for k in list_resp.json()]
    assert key_id not in ids


@pytest.mark.anyio
async def test_delete_nonexistent_key(auth_client: AsyncClient) -> None:
    resp = await auth_client.delete(
        "/api/keys/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_pat_authentication(client: AsyncClient) -> None:
    """A PAT token should authenticate successfully."""
    import uuid

    # Register a user and get JWT
    email = f"pat_{uuid.uuid4().hex[:8]}@example.com"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    token = reg.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    # Create PAT
    create_resp = await client.post(
        "/api/keys", json={"name": "Test PAT", "scope": "full"}
    )
    assert create_resp.status_code == 201
    raw_key = create_resp.json()["raw_key"]

    # Use PAT to authenticate
    client.headers["Authorization"] = f"Bearer {raw_key}"
    list_resp = await client.get("/api/keys")
    assert list_resp.status_code == 200


@pytest.mark.anyio
async def test_invalid_pat_returns_401(client: AsyncClient) -> None:
    client.headers["Authorization"] = "Bearer jv_invalidtoken000000000000000000000"
    resp = await client.get("/api/keys")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_max_keys_enforced(auth_client: AsyncClient) -> None:
    """Creating more than 10 keys should return 409."""
    for i in range(10):
        r = await auth_client.post(
            "/api/keys", json={"name": f"key{i}", "scope": "full"}
        )
        assert r.status_code == 201
    over_limit = await auth_client.post(
        "/api/keys", json={"name": "over", "scope": "full"}
    )
    assert over_limit.status_code == 409
```

**Step 2: Run tests**

```bash
cd backend && uv run pytest tests/api/test_keys.py -v
```

Expected: all tests pass. If any fail, diagnose and fix before continuing.

**Step 3: Run full test suite to check for regressions**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: 0 failures.

**Step 4: Commit**

```bash
git add backend/tests/api/test_keys.py
git commit -m "test(api): add PAT API keys test coverage"
```

---

## Task 7: Frontend API client

**Files:**
- Modify: `frontend/src/api/index.ts`

**Step 1: Add API key types and calls**

Find where other API functions are defined in `frontend/src/api/index.ts` and append:

```typescript
// ─── Personal API Keys ────────────────────────────────────────────────────

export interface ApiKeyItem {
  id: string
  name: string
  prefix: string
  scope: 'full' | 'readonly'
  expires_at: string | null
  last_used_at: string | null
  created_at: string
}

export interface ApiKeyCreateRequest {
  name: string
  scope: 'full' | 'readonly'
  expires_at?: string | null
}

export interface ApiKeyCreateResponse extends ApiKeyItem {
  raw_key: string
}

export const listApiKeys = (): Promise<ApiKeyItem[]> =>
  api.get('/keys').then(r => r.data)

export const createApiKey = (req: ApiKeyCreateRequest): Promise<ApiKeyCreateResponse> =>
  api.post('/keys', req).then(r => r.data)

export const deleteApiKey = (id: string): Promise<void> =>
  api.delete(`/keys/${id}`)
```

**Step 2: Run frontend type check**

```bash
cd frontend && bun run type-check
```

Fix any errors before continuing.

**Step 3: Commit**

```bash
git add frontend/src/api/index.ts
git commit -m "feat(frontend): add Personal API Keys API client functions"
```

---

## Task 8: Frontend Settings page — API Keys section

**Files:**
- Modify: `frontend/src/pages/SettingsPage.vue`

**Step 1: Read the full SettingsPage.vue first to understand structure**

Run: `cat frontend/src/pages/SettingsPage.vue` (or use the Read tool).

**Step 2: Add imports and reactive state to `<script setup>`**

In the `<script setup lang="ts">` block, add the following imports and state (before the existing `onMounted`):

```typescript
import {
  listApiKeys,
  createApiKey,
  deleteApiKey,
  type ApiKeyItem,
  type ApiKeyCreateRequest,
} from '@/api'
import { useI18n } from 'vue-i18n'

// ── PAT state ──────────────────────────────────────────────────────────────
const apiKeysList = ref<ApiKeyItem[]>([])
const showCreateKeyModal = ref(false)
const newKeyName = ref('')
const newKeyScope = ref<'full' | 'readonly'>('full')
const justCreatedKey = ref<string | null>(null)
const keysCopied = ref(false)

async function loadApiKeys() {
  try {
    apiKeysList.value = await listApiKeys()
  } catch {
    // silently ignore on load failure
  }
}

async function handleCreateKey() {
  if (!newKeyName.value.trim()) return
  const req: ApiKeyCreateRequest = {
    name: newKeyName.value.trim(),
    scope: newKeyScope.value,
  }
  const resp = await createApiKey(req)
  justCreatedKey.value = resp.raw_key
  newKeyName.value = ''
  newKeyScope.value = 'full'
  showCreateKeyModal.value = false
  await loadApiKeys()
}

async function handleDeleteKey(id: string) {
  if (!confirm(t('apiKeys.confirmDelete'))) return
  await deleteApiKey(id)
  await loadApiKeys()
}

function copyKey() {
  if (justCreatedKey.value) {
    navigator.clipboard.writeText(justCreatedKey.value)
    keysCopied.value = true
    setTimeout(() => (keysCopied.value = false), 2000)
  }
}

const { t } = useI18n()
```

Also add `loadApiKeys()` call inside `onMounted`.

**Step 3: Add Personal API Keys section to `<template>`**

Append before the closing `</form>` tag, a new section:

```html
<!-- Personal API Keys (PAT) -->
<section class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-6 shadow-sm">
  <div class="flex items-center justify-between mb-6">
    <h3 class="text-[11px] font-bold tracking-widest text-zinc-500 uppercase">
      {{ $t('apiKeys.title') }}
    </h3>
    <button
      type="button"
      class="text-xs font-medium px-3 py-1.5 bg-blue-600/20 text-blue-400 rounded-lg hover:bg-blue-600/30 transition-colors"
      @click="showCreateKeyModal = true"
    >
      + {{ $t('apiKeys.create') }}
    </button>
  </div>

  <p class="text-xs text-zinc-500 mb-4">{{ $t('apiKeys.description') }}</p>

  <!-- Key list -->
  <div v-if="apiKeysList.length === 0" class="text-xs text-zinc-600 italic">
    {{ $t('apiKeys.empty') }}
  </div>
  <div v-else class="space-y-2">
    <div
      v-for="key in apiKeysList"
      :key="key.id"
      class="flex items-center justify-between bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3"
    >
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <span class="text-sm font-medium text-zinc-200 truncate">{{ key.name }}</span>
          <span
            class="text-[10px] px-1.5 py-0.5 rounded font-mono"
            :class="key.scope === 'readonly' ? 'bg-amber-500/20 text-amber-400' : 'bg-green-500/20 text-green-400'"
          >{{ key.scope }}</span>
        </div>
        <div class="text-xs text-zinc-500 font-mono mt-0.5">
          {{ key.prefix }}••••••••
          <span v-if="key.last_used_at" class="ml-3 font-sans">
            {{ $t('apiKeys.lastUsed') }}: {{ new Date(key.last_used_at).toLocaleDateString() }}
          </span>
        </div>
      </div>
      <button
        type="button"
        class="ml-4 text-xs text-red-400 hover:text-red-300 transition-colors"
        @click="handleDeleteKey(key.id)"
      >
        {{ $t('apiKeys.revoke') }}
      </button>
    </div>
  </div>
</section>

<!-- Create Key Modal -->
<Teleport to="body">
  <div v-if="showCreateKeyModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
    <div class="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 w-full max-w-sm mx-4 shadow-xl">
      <h4 class="text-sm font-semibold text-zinc-200 mb-4">{{ $t('apiKeys.createTitle') }}</h4>
      <div class="space-y-3">
        <input
          v-model="newKeyName"
          type="text"
          class="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600"
          :placeholder="$t('apiKeys.namePlaceholder')"
        />
        <select
          v-model="newKeyScope"
          class="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600"
        >
          <option value="full">full — {{ $t('apiKeys.scopeFull') }}</option>
          <option value="readonly">readonly — {{ $t('apiKeys.scopeReadonly') }}</option>
        </select>
      </div>
      <div class="flex gap-3 mt-5">
        <button
          type="button"
          class="flex-1 py-2.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-500 transition-colors"
          @click="handleCreateKey"
        >{{ $t('apiKeys.create') }}</button>
        <button
          type="button"
          class="flex-1 py-2.5 text-sm bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 transition-colors"
          @click="showCreateKeyModal = false"
        >{{ $t('common.cancel') }}</button>
      </div>
    </div>
  </div>
</Teleport>

<!-- One-time key reveal modal -->
<Teleport to="body">
  <div v-if="justCreatedKey" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
    <div class="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 w-full max-w-md mx-4 shadow-xl">
      <h4 class="text-sm font-semibold text-zinc-200 mb-2">{{ $t('apiKeys.revealTitle') }}</h4>
      <p class="text-xs text-amber-400 mb-4">{{ $t('apiKeys.revealWarning') }}</p>
      <div class="flex items-center gap-2 bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-3">
        <code class="flex-1 text-xs font-mono text-green-400 break-all">{{ justCreatedKey }}</code>
        <button type="button" @click="copyKey" class="text-xs text-zinc-400 hover:text-zinc-200 transition-colors whitespace-nowrap">
          {{ keysCopied ? $t('common.copied') : $t('common.copy') }}
        </button>
      </div>
      <button
        type="button"
        class="w-full mt-4 py-2.5 text-sm bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 transition-colors"
        @click="justCreatedKey = null"
      >{{ $t('common.close') }}</button>
    </div>
  </div>
</Teleport>
```

**Step 4: Run frontend checks**

```bash
cd frontend && bun run lint:fix && bun run type-check
```

Fix any errors before continuing.

**Step 5: Commit**

```bash
git add frontend/src/pages/SettingsPage.vue
git commit -m "feat(frontend): add Personal API Keys management section in Settings"
```

---

## Task 9: i18n strings

**Files:**
- Modify: `frontend/src/locales/zh.json`
- Modify: `frontend/src/locales/en.json`
- Modify: `frontend/src/locales/ja.json`
- Modify: `frontend/src/locales/ko.json`
- Modify: `frontend/src/locales/fr.json`
- Modify: `frontend/src/locales/de.json`

**Step 1: Read each locale file and add `apiKeys` section + `common.cancel/copy/copied/close` if missing**

For each locale, add inside the JSON object:

**zh.json** — add at root level:
```json
"apiKeys": {
  "title": "个人 API 密钥",
  "description": "创建长效令牌，用于脚本或第三方工具访问 JARVIS API。",
  "create": "新建密钥",
  "createTitle": "新建 API 密钥",
  "namePlaceholder": "密钥名称（如：我的脚本）",
  "scopeFull": "完整访问",
  "scopeReadonly": "只读访问",
  "empty": "暂无 API 密钥",
  "lastUsed": "最近使用",
  "revoke": "撤销",
  "confirmDelete": "确定要撤销这个 API 密钥吗？此操作不可恢复。",
  "revealTitle": "你的新 API 密钥",
  "revealWarning": "请立即复制，此密钥不会再次显示。"
}
```

Also add to `common` section (if not already present):
```json
"cancel": "取消",
"copy": "复制",
"copied": "已复制！",
"close": "关闭"
```

**en.json** — add:
```json
"apiKeys": {
  "title": "Personal API Keys",
  "description": "Create long-lived tokens for scripts or third-party tools to access the JARVIS API.",
  "create": "New Key",
  "createTitle": "Create API Key",
  "namePlaceholder": "Key name (e.g. My Script)",
  "scopeFull": "Full access",
  "scopeReadonly": "Read-only access",
  "empty": "No API keys yet",
  "lastUsed": "Last used",
  "revoke": "Revoke",
  "confirmDelete": "Revoke this API key? This cannot be undone.",
  "revealTitle": "Your New API Key",
  "revealWarning": "Copy it now — it won't be shown again."
}
```

Common: `"cancel": "Cancel", "copy": "Copy", "copied": "Copied!", "close": "Close"`

**ja.json** — add:
```json
"apiKeys": {
  "title": "個人APIキー",
  "description": "スクリプトやツールからJARVIS APIにアクセスするための長期トークンを作成します。",
  "create": "新規作成",
  "createTitle": "APIキーを作成",
  "namePlaceholder": "キー名（例：マイスクリプト）",
  "scopeFull": "フルアクセス",
  "scopeReadonly": "読み取り専用",
  "empty": "APIキーがありません",
  "lastUsed": "最終使用",
  "revoke": "失効",
  "confirmDelete": "このAPIキーを失効させますか？元に戻せません。",
  "revealTitle": "新しいAPIキー",
  "revealWarning": "今すぐコピーしてください。再表示されません。"
}
```

Common: `"cancel": "キャンセル", "copy": "コピー", "copied": "コピー済み！", "close": "閉じる"`

**ko.json** — add:
```json
"apiKeys": {
  "title": "개인 API 키",
  "description": "스크립트나 도구에서 JARVIS API에 접근하기 위한 장기 토큰을 생성합니다.",
  "create": "새 키 만들기",
  "createTitle": "API 키 생성",
  "namePlaceholder": "키 이름 (예: 내 스크립트)",
  "scopeFull": "전체 접근",
  "scopeReadonly": "읽기 전용",
  "empty": "API 키가 없습니다",
  "lastUsed": "마지막 사용",
  "revoke": "폐기",
  "confirmDelete": "이 API 키를 폐기하시겠습니까? 되돌릴 수 없습니다.",
  "revealTitle": "새 API 키",
  "revealWarning": "지금 복사하세요. 다시 표시되지 않습니다."
}
```

Common: `"cancel": "취소", "copy": "복사", "copied": "복사됨!", "close": "닫기"`

**fr.json** — add:
```json
"apiKeys": {
  "title": "Clés API personnelles",
  "description": "Créez des jetons durables pour accéder à l'API JARVIS depuis des scripts ou outils tiers.",
  "create": "Nouvelle clé",
  "createTitle": "Créer une clé API",
  "namePlaceholder": "Nom de la clé (ex : Mon script)",
  "scopeFull": "Accès complet",
  "scopeReadonly": "Lecture seule",
  "empty": "Aucune clé API",
  "lastUsed": "Dernière utilisation",
  "revoke": "Révoquer",
  "confirmDelete": "Révoquer cette clé API ? Cette action est irréversible.",
  "revealTitle": "Votre nouvelle clé API",
  "revealWarning": "Copiez-la maintenant, elle ne sera plus affichée."
}
```

Common: `"cancel": "Annuler", "copy": "Copier", "copied": "Copié !", "close": "Fermer"`

**de.json** — add:
```json
"apiKeys": {
  "title": "Persönliche API-Schlüssel",
  "description": "Erstellen Sie langlebige Token für Skripte oder Drittanbieter-Tools.",
  "create": "Neuer Schlüssel",
  "createTitle": "API-Schlüssel erstellen",
  "namePlaceholder": "Schlüsselname (z. B. Mein Skript)",
  "scopeFull": "Vollzugriff",
  "scopeReadonly": "Nur Lesezugriff",
  "empty": "Keine API-Schlüssel vorhanden",
  "lastUsed": "Zuletzt verwendet",
  "revoke": "Widerrufen",
  "confirmDelete": "Diesen API-Schlüssel widerrufen? Dies kann nicht rückgängig gemacht werden.",
  "revealTitle": "Ihr neuer API-Schlüssel",
  "revealWarning": "Kopieren Sie ihn jetzt — er wird nicht mehr angezeigt."
}
```

Common: `"cancel": "Abbrechen", "copy": "Kopieren", "copied": "Kopiert!", "close": "Schließen"`

**Step 2: Run type-check**

```bash
cd frontend && bun run type-check
```

**Step 3: Commit**

```bash
git add frontend/src/locales/
git commit -m "i18n: add Personal API Keys translations for all 6 locales"
```

---

## Task 10: Final verification and PR

**Step 1: Run full backend test suite**

```bash
cd backend && uv run pytest tests/ -v 2>&1 | tail -30
```

Expected: 0 failures.

**Step 2: Run full static analysis**

```bash
cd backend && uv run ruff check && uv run ruff format --check
cd backend && uv run mypy app
cd frontend && bun run lint && bun run type-check
```

**Step 3: Pre-commit hooks**

```bash
cd /path/to/worktree && pre-commit run --all-files
```

**Step 4: Push and create PR**

```bash
git push -u origin feature/api-keys
gh pr create \
  --base dev \
  --title "feat: Phase 12.4 — Personal API Keys (PAT)" \
  --body "$(cat <<'EOF'
## Summary
- New `api_keys` table with sha256-hashed PAT storage
- `jv_<64hex>` token format; tokens never stored in plaintext
- `full` and `readonly` scope support; scope stored in `request.state` for future enforcement
- `GET/POST/DELETE /api/keys` — max 10 keys per user
- `Bearer jv_xxx` tokens recognized in `_resolve_user` alongside JWTs
- Settings page: Personal API Keys section with create/revoke UI and one-time reveal modal
- 6-locale i18n support

## Test plan
- [ ] `uv run pytest tests/api/test_keys.py -v` — all tests pass
- [ ] `uv run pytest tests/ -v` — 0 regressions
- [ ] Create key via Settings UI, copy raw key, use it in `curl -H "Authorization: Bearer jv_..."`, verify success
- [ ] Verify key appears in list with prefix but not raw value
- [ ] Revoke key, verify subsequent requests return 401

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Notes for Implementer

- **`_resolve_user` in deps.py**: The `Request` parameter is injected by FastAPI automatically when declared without a default. Do NOT use `Depends()` for `Request`.
- **`await db.commit()` in `_resolve_pat`**: This commits the `last_used_at` update immediately. Since it runs in the auth dependency before any handler logic, the main handler gets a clean session state.
- **Scope enforcement**: V1 stores and displays scope but does not block requests based on it (except that PAT key creation itself checks nothing — a readonly key CAN list and delete keys). Enforcement of `readonly` on non-key endpoints is future work. Add a TODO comment in `deps.py`.
- **`prefix` field**: Stores the first 8 chars of the raw token (`jv_XXXXX`), enough to identify a key without revealing the secret. The full raw key has 67 chars total.
- **test_pat_authentication**: This test uses the `client` fixture (not `auth_client`) because it needs to swap headers mid-test.
