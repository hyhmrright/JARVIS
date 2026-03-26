# Phase 21B: Data Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add (1) a 1000-message cap with `truncated` field to the existing per-conversation export endpoint, and (2) a full account export system (`POST /api/export/account`) that packages all user data into a ZIP via an ARQ background worker, stores it in MinIO, and notifies the user with a 25-hour presigned download link.

**Architecture:** The existing `GET /api/conversations/{conv_id}/export` in `conversations.py` is extended with a 1000-message cap. A new `export.py` contains account export endpoints only. A new ARQ task `export_account` writes a ZIP to a temp file (not memory), uploads to MinIO, and inserts a `Notification`. A new `Notification` type enum value is added via Alembic migration. Cooldown enforcement uses Redis `SET NX` atomically. The cleanup cron uses a Redis Sorted Set to track pending MinIO deletions.

**Tech Stack:** FastAPI, SQLAlchemy async, ARQ (background jobs), Redis (cooldown + status + cleanup tracking), MinIO (minio-py SDK, sync + `asyncio.to_thread`), zipfile + tempfile, Vue 3, pytest-anyio

---

## File Map

**Create:**
- `backend/app/api/export.py` — account export endpoints
- `backend/alembic/versions/d2e3f4a5b6c7_add_export_notification_types.py` — add notification types to CHECK constraint
- `backend/tests/api/test_export.py` — export tests

**Modify:**
- `backend/app/api/conversations.py` — extend export endpoint with 1000-message cap
- `backend/app/worker.py` — add `export_account` task + `cleanup_expired_exports` cron
- `backend/app/main.py` — register `export_router`
- `frontend/src/pages/ChatPage.vue` — add per-conversation export button
- `frontend/src/pages/SettingsPage.vue` — add account export section
- `frontend/src/locales/zh.json`, `en.json`, `ja.json`, `ko.json`, `fr.json`, `de.json` — add `export.*` keys

---

## Task 1: Alembic Migration — Add Export Notification Types

**Files:**
- Create: `backend/alembic/versions/d2e3f4a5b6c7_add_export_notification_types.py`

**Context:** The `Notification` model has a `CheckConstraint` that only allows specific `type` values:
```
'cron_completed','cron_failed','webhook_failed','invitation_received','workflow_completed','workflow_failed'
```
We need to add `'account_export_ready'` and `'account_export_failed'`. In PostgreSQL, `ALTER TABLE ... DROP CONSTRAINT ... ADD CONSTRAINT` is the only way to change a CHECK constraint.

**Important:** After running this migration, also update the `CheckConstraint` in `backend/app/db/models.py` to match the new allowed values, otherwise SQLAlchemy model validation may diverge from the DB.

- [ ] **Step 1: Create migration file**

```python
# backend/alembic/versions/d2e3f4a5b6c7_add_export_notification_types.py
"""Add account_export_ready and account_export_failed notification types

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-03-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

_OLD_TYPES = (
    "'cron_completed','cron_failed','webhook_failed',"
    "'invitation_received','workflow_completed','workflow_failed'"
)
_NEW_TYPES = (
    "'cron_completed','cron_failed','webhook_failed',"
    "'invitation_received','workflow_completed','workflow_failed',"
    "'account_export_ready','account_export_failed'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE notifications DROP CONSTRAINT IF EXISTS ck_notifications_type")
    op.execute(
        f"ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type "
        f"CHECK (type IN ({_NEW_TYPES}))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE notifications DROP CONSTRAINT IF EXISTS ck_notifications_type")
    op.execute(
        f"ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type "
        f"CHECK (type IN ({_OLD_TYPES}))"
    )
```

- [ ] **Step 2: Update the CheckConstraint in db/models.py**

In `backend/app/db/models.py`, find the `Notification` class `__table_args__` and update the `CheckConstraint`:

```python
# Old:
CheckConstraint(
    "type IN ('cron_completed','cron_failed','webhook_failed',"
    "'invitation_received','workflow_completed','workflow_failed')",
    name="ck_notifications_type",
),
# New:
CheckConstraint(
    "type IN ('cron_completed','cron_failed','webhook_failed',"
    "'invitation_received','workflow_completed','workflow_failed',"
    "'account_export_ready','account_export_failed')",
    name="ck_notifications_type",
),
```

- [ ] **Step 3: Run the migration**

```bash
cd backend
uv run alembic upgrade head
# Expected: runs without error
```

- [ ] **Step 4: Commit**

```bash
git add \
  backend/alembic/versions/d2e3f4a5b6c7_add_export_notification_types.py \
  backend/app/db/models.py
git commit -m "feat: add account_export notification types to CHECK constraint"
```

---

## Task 2: Extend Existing Conversation Export with 1000-Message Cap

**Files:**
- Modify: `backend/app/api/conversations.py` (around line 316)
- Test: `backend/tests/api/test_conversations.py` (extend existing file)

**Context:** The existing `export_conversation` function fetches all messages and formats them. We need to:
1. Add a `LIMIT 1000` to the query (ordered by `created_at DESC` to get the most recent, then reverse for display)
2. Add `truncated: bool` to the JSON output
3. Add a truncation note to the Markdown header when `truncated=True`
4. The existing `format` parameter accepts `"md"`, `"json"`, `"txt"` — keep those working

- [ ] **Step 1: Write failing tests (append to test_conversations.py)**

```python
# Append to backend/tests/api/test_conversations.py

@pytest.mark.anyio
async def test_export_conversation_markdown(auth_client, db_session):
    """Export conversation as Markdown, returns correct Content-Disposition."""
    uid = _user_id(auth_client)
    conv = Conversation(user_id=uid, title="Export Test Conv")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(Message(conversation_id=conv.id, role="human", content="Hello world"))
    db_session.add(Message(conversation_id=conv.id, role="ai", content="Hi there!"))
    await db_session.commit()

    resp = await auth_client.get(f"/api/conversations/{conv.id}/export?format=md")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("content-disposition", "")
    body = resp.text
    assert "Export Test Conv" in body
    assert "Hello world" in body
    assert "Hi there!" in body


@pytest.mark.anyio
async def test_export_conversation_truncated(auth_client, db_session):
    """Export with >1000 messages: returns most recent 1000, includes truncation note."""
    uid = _user_id(auth_client)
    conv = Conversation(user_id=uid, title="Big Conv")
    db_session.add(conv)
    await db_session.flush()
    # Create 1005 messages
    for i in range(1005):
        db_session.add(Message(
            conversation_id=conv.id, role="human", content=f"msg {i}"
        ))
    await db_session.commit()

    resp = await auth_client.get(f"/api/conversations/{conv.id}/export?format=md")
    assert resp.status_code == 200
    body = resp.text
    # Should mention truncation
    assert "1000" in body
    assert "1005" in body


@pytest.mark.anyio
async def test_export_conversation_json_truncated_field(auth_client, db_session):
    """JSON export includes truncated field."""
    uid = _user_id(auth_client)
    conv = Conversation(user_id=uid, title="JSON Export")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(Message(conversation_id=conv.id, role="human", content="hi"))
    await db_session.commit()

    resp = await auth_client.get(f"/api/conversations/{conv.id}/export?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert "truncated" in data
    assert data["truncated"] is False  # only 1 message, not truncated


@pytest.mark.anyio
async def test_export_other_user_conversation_returns_404(
    auth_client, second_user_auth_headers, client, db_session
):
    """Cannot export another user's conversation."""
    import uuid as _uuid
    from app.core.security import decode_access_token as _dat
    token2 = second_user_auth_headers["Authorization"].split(" ")[1]
    uid2 = _uuid.UUID(_dat(token2))
    conv2 = Conversation(user_id=uid2, title="User2 Private")
    db_session.add(conv2)
    await db_session.commit()

    resp = await auth_client.get(f"/api/conversations/{conv2.id}/export?format=md")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend
uv run pytest tests/api/test_conversations.py::test_export_conversation_truncated -v
# Expected: FAIL — no truncation in current implementation
```

- [ ] **Step 3: Update the export_conversation function in conversations.py**

Find `async def export_conversation` (around line 316). The key changes:

1. Change the message query to order `DESC` with `LIMIT 1001` (fetch one extra to detect truncation):

```python
# Replace the existing rows query with:
rows = await db.scalars(
    select(Message)
    .where(
        Message.conversation_id == conv_id,
        Message.role.in_(["human", "ai"]),
    )
    .order_by(Message.created_at.desc())
    .limit(1001)
)
messages_desc = list(rows.all())
truncated = len(messages_desc) > 1000
messages = list(reversed(messages_desc[:1000]))
total_fetched = len(messages_desc)
```

2. Update the Markdown format block to add metadata header and truncation note:

```python
if format == "md":
    truncation_note = (
        f" (showing most recent 1000 of {total_fetched} messages)"
        if truncated
        else ""
    )
    lines = [
        f"# {conv.title}",
        "",
        f"> Exported: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        f"> Messages: {len(messages)}{truncation_note}",
        "",
        "---",
        "",
    ]
    for msg in messages:
        prefix = "**Human:**" if msg.role == "human" else "**Assistant:**"
        lines.append(f"{prefix}\n{msg.content}")
        lines.append("")
    return Response(
        content="\n".join(lines),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
    )
```

3. Update the JSON format block to add `truncated` and `exported_at`:

```python
elif format == "json":
    data = {
        "id": str(conv.id),
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "exported_at": datetime.now(UTC).isoformat(),
        "truncated": truncated,
        "messages": [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ],
    }
    disposition = f'attachment; filename="{safe_title}.json"'
    return Response(
        content=_json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": disposition},
    )
```

Also add `from datetime import UTC, datetime` if not already imported (check existing imports at the top of `conversations.py`).

- [ ] **Step 4: Run tests**

```bash
cd backend
uv run pytest tests/api/test_conversations.py -v -k "export" --tb=short
# Expected: all export tests PASS
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/conversations.py backend/tests/api/test_conversations.py
git commit -m "feat: add 1000-message cap and truncated field to conversation export"
```

---

## Task 3: Account Export API Endpoints

**Files:**
- Create: `backend/app/api/export.py`
- Test: `backend/tests/api/test_export.py`

**Context:**
- Redis access pattern (from `gateway.py`): `Redis.from_url(get_redis_url(), decode_responses=True)`
- `get_redis_url()` is from `app.infra.redis`
- Cooldown key: `export_cooldown:{user_id}` (TTL 86400s, `SET NX`)
- Status key: `export_status:{user_id}` (TTL 90000s = 25h, JSON string)
- The `POST` endpoint enqueues an ARQ job — use `ArqRedis` (imported from `arq`). See how `cron.py` enqueues jobs: it uses the `redis` dependency.
- No `task_id` is returned in the POST response (status is keyed by user_id only)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/api/test_export.py
"""Tests for the account export endpoints."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import decode_access_token


def _uid(auth_client) -> uuid.UUID:
    token = auth_client.headers["Authorization"].split(" ")[1]
    return uuid.UUID(decode_access_token(token))


@pytest.mark.anyio
async def test_account_export_requires_auth(client):
    resp = await client.post("/api/export/account")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_account_export_enqueues_job(auth_client):
    """POST /api/export/account enqueues ARQ job and returns 200."""
    with (
        patch("app.api.export._get_redis_client") as mock_redis_fn,
        patch("app.api.export._enqueue_export") as mock_enqueue,
    ):
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True  # SET NX succeeds (not in cooldown)
        mock_redis.get.return_value = None  # no existing status
        mock_redis_fn.return_value = mock_redis
        mock_enqueue.return_value = None

        resp = await auth_client.post("/api/export/account")
        assert resp.status_code == 200
        assert "message" in resp.json()


@pytest.mark.anyio
async def test_account_export_cooldown(auth_client):
    """Second request within 24h returns 429 with retry_after."""
    with patch("app.api.export._get_redis_client") as mock_redis_fn:
        mock_redis = AsyncMock()
        # SET NX fails — key already exists (cooldown active)
        mock_redis.set.return_value = None
        mock_redis.ttl.return_value = 3600  # 1 hour remaining
        mock_redis_fn.return_value = mock_redis

        resp = await auth_client.post("/api/export/account")
        assert resp.status_code == 429
        body = resp.json()
        assert "retry_after" in body["detail"] or "retry_after" in body


@pytest.mark.anyio
async def test_account_export_status_no_prior_export(auth_client):
    """GET /api/export/account/status returns 200 with pending-like status when no prior export."""
    with patch("app.api.export._get_redis_client") as mock_redis_fn:
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # no status key
        mock_redis_fn.return_value = mock_redis

        resp = await auth_client.get("/api/export/account/status")
        assert resp.status_code == 200


@pytest.mark.anyio
async def test_account_export_status_done(auth_client):
    """GET /api/export/account/status returns done status with download_url."""
    import json as _json
    status_data = {
        "status": "done",
        "created_at": "2026-03-26T10:00:00",
        "download_url": "https://minio.example.com/presigned",
        "expires_at": "2026-03-27T11:00:00",
    }
    with patch("app.api.export._get_redis_client") as mock_redis_fn:
        mock_redis = AsyncMock()
        mock_redis.get.return_value = _json.dumps(status_data)
        mock_redis_fn.return_value = mock_redis

        resp = await auth_client.get("/api/export/account/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "done"
        assert body["download_url"] == "https://minio.example.com/presigned"
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend
uv run pytest tests/api/test_export.py -v 2>&1 | head -20
# Expected: FAIL / ImportError — no app.api.export module
```

- [ ] **Step 3: Implement export.py**

```python
# backend/app/api/export.py
"""Account export endpoints: trigger background export and check status."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.models import User
from app.db.session import get_db
from app.infra.redis import get_redis_url

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/export", tags=["export"])

_COOLDOWN_TTL = 86400  # 24 hours in seconds
_STATUS_TTL = 90000    # 25 hours in seconds


def _cooldown_key(user_id: uuid.UUID) -> str:
    return f"export_cooldown:{user_id}"


def _status_key(user_id: uuid.UUID) -> str:
    return f"export_status:{user_id}"


async def _get_redis_client() -> Redis:
    return Redis.from_url(get_redis_url(), decode_responses=True)


async def _enqueue_export(user_id: str) -> None:
    """Enqueue the export_account ARQ task."""
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job("export_account", user_id=user_id)
    await pool.aclose()


class ExportStartResponse(BaseModel):
    message: str


class ExportStatusResponse(BaseModel):
    status: str  # pending | running | done | failed | none
    created_at: str | None = None
    download_url: str | None = None
    expires_at: str | None = None


@router.post("/account", response_model=ExportStartResponse)
@limiter.limit("5/minute")
async def start_account_export(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExportStartResponse:
    """Trigger a full account data export. Rate-limited to once per 24 hours."""
    redis = await _get_redis_client()
    try:
        cooldown_key = _cooldown_key(user.id)
        # Atomic SET NX: returns True if key was set (not in cooldown), None/False if already exists
        set_result = await redis.set(cooldown_key, "1", ex=_COOLDOWN_TTL, nx=True)
        if not set_result:
            ttl = await redis.ttl(cooldown_key)
            raise HTTPException(
                status_code=429,
                detail={"message": "Export already requested.", "retry_after": max(ttl, 0)},
            )

        # Set initial status
        status_data = {
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
        }
        await redis.set(_status_key(user.id), json.dumps(status_data), ex=_STATUS_TTL)

        # Enqueue ARQ job — user_id extracted server-side, never from client input
        await _enqueue_export(str(user.id))

        logger.info("account_export_started", user_id=str(user.id))
        return ExportStartResponse(
            message="Export started. You will be notified when ready."
        )
    finally:
        await redis.aclose()


@router.get("/account/status", response_model=ExportStatusResponse)
@limiter.limit("30/minute")
async def get_account_export_status(
    request: Request,
    user: User = Depends(get_current_user),
) -> ExportStatusResponse:
    """Check the status of the most recent account export."""
    redis = await _get_redis_client()
    try:
        raw = await redis.get(_status_key(user.id))
        if not raw:
            return ExportStatusResponse(status="none")
        data = json.loads(raw)
        return ExportStatusResponse(
            status=data.get("status", "unknown"),
            created_at=data.get("created_at"),
            download_url=data.get("download_url"),
            expires_at=data.get("expires_at"),
        )
    finally:
        await redis.aclose()
```

- [ ] **Step 4: Register export router in main.py**

In `backend/app/main.py`, add:

```python
from app.api.export import router as export_router
```

And:

```python
app.include_router(export_router)
```

- [ ] **Step 5: Run import check and tests**

```bash
cd backend
uv run pytest --collect-only -q 2>&1 | tail -5
uv run pytest tests/api/test_export.py -v
# Expected: all pass
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/export.py backend/app/main.py backend/tests/api/test_export.py
git commit -m "feat: add account export trigger and status endpoints"
```

---

## Task 4: ARQ Worker — export_account Task + cleanup_expired_exports Cron

**Files:**
- Modify: `backend/app/worker.py`

**Context:**
- Existing ARQ tasks use `ctx["redis"]` for Redis access and `ctx["job_id"]` for the job ID
- MinIO client is sync — wrap with `asyncio.to_thread()`
- `minio_client.presigned_get_object(bucket, object_key, expires=timedelta(hours=25))` generates presigned URL
- ZIP: use `tempfile.NamedTemporaryFile` (not `io.BytesIO`) to avoid memory pressure
- Cleanup cron: uses Redis Sorted Set `export_pending_cleanup` with score = expiry timestamp
- `Notification` model fields: `user_id`, `type`, `title`, `body`, `action_url`, `metadata_json`
- After adding to `worker.py`, also add the task to `WorkerSettings.functions` and cron to `WorkerSettings.cron_jobs`

- [ ] **Step 1: Add import and helper functions at top of worker.py**

Add these imports after the existing imports in `worker.py`:

```python
import asyncio
import io
import json
import tempfile
import uuid
import zipfile
from datetime import timedelta

from sqlalchemy import select

from app.db.models import Conversation, Document, Message, Notification, UserMemory, UserSettings
from app.db.session import AsyncSessionLocal
from app.infra.minio import get_minio_client
from app.infra.redis import get_redis_url
from app.core.config import settings as _settings
```

(Check which of these are already imported and avoid duplicates.)

- [ ] **Step 2: Add export_account function to worker.py**

Add before `class WorkerSettings`:

```python
_EXPORT_STATUS_TTL = 90000  # 25 hours
_CLEANUP_ZSET_KEY = "export_pending_cleanup"


async def export_account(ctx: dict, *, user_id: str) -> None:
    """ARQ task: package all user data into a ZIP, upload to MinIO, notify user."""
    uid = uuid.UUID(user_id)
    redis = ctx["redis"]
    task_id = str(uuid.uuid4())  # unique identifier for this export's MinIO object key
    logger.info("export_account_started", user_id=user_id, task_id=task_id)

    async def _set_status(status: str, **extra: object) -> None:
        from datetime import UTC, datetime
        data = {"status": status, "created_at": datetime.now(UTC).isoformat(), **extra}
        await redis.set(f"export_status:{user_id}", json.dumps(data), ex=_EXPORT_STATUS_TTL)

    await _set_status("running")

    try:
        async with AsyncSessionLocal() as db:
            # 1. Conversations + messages
            conv_rows = await db.scalars(
                select(Conversation).where(Conversation.user_id == uid)
            )
            conversations = list(conv_rows.all())
            conv_files: dict[str, str] = {}  # filename -> markdown content

            for conv in conversations:
                msg_rows = await db.scalars(
                    select(Message)
                    .where(
                        Message.conversation_id == conv.id,
                        Message.role.in_(["human", "ai"]),
                    )
                    .order_by(Message.created_at)
                )
                msgs = list(msg_rows.all())
                safe_title = conv.title.replace("/", "_").replace("\\", "_")[:80]
                date_prefix = conv.created_at.strftime("%Y-%m-%d")
                lines = [
                    f"# {conv.title}",
                    f"> Created: {conv.created_at.isoformat()}",
                    "",
                ]
                for msg in msgs:
                    prefix = "**用户**" if msg.role == "human" else "**助手**"
                    lines.append(f"{prefix} · {msg.created_at.strftime('%Y-%m-%d %H:%M')}")
                    lines.append(msg.content)
                    lines.append("")
                conv_files[f"conversations/{date_prefix}_{safe_title}.md"] = "\n".join(lines)

            # 2. Documents metadata
            doc_rows = await db.scalars(
                select(Document).where(
                    Document.user_id == uid,
                    Document.is_deleted.is_(False),
                )
            )
            docs_data = [
                {
                    "id": str(d.id),
                    "filename": d.filename,
                    "file_type": d.file_type,
                    "file_size_bytes": d.file_size_bytes,
                    "chunk_count": d.chunk_count,
                    "created_at": d.created_at.isoformat(),
                    "source_url": d.source_url,
                }
                for d in doc_rows.all()
            ]

            # 3. Memories
            mem_rows = await db.scalars(
                select(UserMemory).where(UserMemory.user_id == uid)
            )
            memories_data = [
                {
                    "id": str(m.id),
                    "key": m.key,
                    "value": m.value,
                    "category": m.category,
                    "created_at": m.created_at.isoformat(),
                }
                for m in mem_rows.all()
            ]

            # 4. Settings (api_keys redacted)
            user_settings = await db.scalar(
                select(UserSettings).where(UserSettings.user_id == uid)
            )
            settings_data: dict = {}
            if user_settings:
                settings_data = {
                    "model_provider": user_settings.model_provider,
                    "model_name": user_settings.model_name,
                    "api_keys": "[REDACTED]",
                    "enabled_tools": user_settings.enabled_tools,
                    "persona_override": user_settings.persona_override,
                }

        # 5. Build ZIP using temp file (not BytesIO — avoids memory pressure)
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = tmp.name

        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in conv_files.items():
                zf.writestr(name, content)
            zf.writestr("documents.json", json.dumps(docs_data, ensure_ascii=False, indent=2))
            zf.writestr("memories.json", json.dumps(memories_data, ensure_ascii=False, indent=2))
            zf.writestr("settings.json", json.dumps(settings_data, ensure_ascii=False, indent=2))

        # 6. Upload to MinIO
        object_key = f"exports/{user_id}/{task_id}.zip"
        minio_client = get_minio_client()
        with open(tmp_path, "rb") as f:
            file_size = f.seek(0, 2)
            f.seek(0)
            await asyncio.to_thread(
                minio_client.put_object,
                _settings.minio_bucket,
                object_key,
                f,
                file_size,
            )

        # Clean up temp file
        import os
        os.unlink(tmp_path)

        # 7. Presigned URL (25 hours)
        download_url = await asyncio.to_thread(
            minio_client.presigned_get_object,
            _settings.minio_bucket,
            object_key,
            expires=timedelta(hours=25),
        )

        # 8. Track for cleanup (Redis sorted set with score = expiry timestamp)
        from datetime import UTC, datetime
        expiry_ts = (datetime.now(UTC) + timedelta(hours=25)).timestamp()
        await redis.zadd(_CLEANUP_ZSET_KEY, {object_key: expiry_ts})

        expires_at = (datetime.now(UTC) + timedelta(hours=25)).isoformat()

        # 9. Notify user
        async with AsyncSessionLocal() as db:
            db.add(Notification(
                user_id=uid,
                type="account_export_ready",
                title="数据导出已就绪",
                body=f"您的数据导出已完成，请在25小时内下载。",
                action_url=download_url[:200],  # URL may be long — trim to model limit
                metadata_json={"download_url": download_url, "expires_at": expires_at},
            ))
            await db.commit()

        # 10. Update Redis status
        await _set_status("done", download_url=download_url, expires_at=expires_at)
        logger.info("export_account_done", user_id=user_id, task_id=task_id)

    except Exception:
        logger.exception("export_account_failed", user_id=user_id, task_id=task_id)
        await _set_status("failed")
        try:
            async with AsyncSessionLocal() as db:
                db.add(Notification(
                    user_id=uid,
                    type="account_export_failed",
                    title="数据导出失败",
                    body="导出过程中发生错误，请稍后重试。",
                    metadata_json={},
                ))
                await db.commit()
        except Exception:
            logger.exception("export_failure_notification_failed", user_id=user_id)


async def cleanup_expired_exports(ctx: dict) -> None:
    """Hourly cron: delete expired MinIO export objects tracked in Redis sorted set."""
    from datetime import UTC, datetime
    redis = ctx["redis"]
    now_ts = datetime.now(UTC).timestamp()

    # Get all object keys whose cleanup time has passed
    expired_keys = await redis.zrangebyscore(_CLEANUP_ZSET_KEY, 0, now_ts)
    if not expired_keys:
        return

    minio_client = get_minio_client()
    for object_key in expired_keys:
        try:
            await asyncio.to_thread(
                minio_client.remove_object,
                _settings.minio_bucket,
                object_key,
            )
            await redis.zrem(_CLEANUP_ZSET_KEY, object_key)
            logger.info("export_cleanup_deleted", object_key=object_key)
        except Exception:
            # Leave key in sorted set — will retry next hour
            logger.warning("export_cleanup_failed", object_key=object_key, exc_info=True)
```

- [ ] **Step 3: Register in WorkerSettings**

Update `WorkerSettings` in `worker.py`:

```python
class WorkerSettings:
    functions = [execute_cron_job, deliver_webhook, export_account]  # add export_account
    cron_jobs = [
        cron(cleanup_old_executions, hour=3, minute=0),
        cron(cleanup_old_deliveries, hour=3, minute=15),
        cron(cleanup_expired_exports, minute=0),  # add: every hour at :00
    ]
    # ... rest unchanged
```

- [ ] **Step 4: Run lint and type check**

```bash
cd backend
uv run ruff check --fix && uv run ruff format && uv run mypy app
# Expected: no errors
```

- [ ] **Step 5: Run import check**

```bash
cd backend
uv run pytest --collect-only -q 2>&1 | tail -5
# Expected: no import errors
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/worker.py
git commit -m "feat: add export_account ARQ task and cleanup_expired_exports cron"
```

---

## Task 5: Frontend — Conversation Export Button + Account Export Settings

**Files:**
- Modify: `frontend/src/pages/ChatPage.vue` — add export button in conversation header
- Modify: `frontend/src/pages/SettingsPage.vue` — add account export section
- Modify: `frontend/src/locales/*.json` (×6) — add `export.*` keys

**Context:**
- The per-conversation export calls the existing endpoint `GET /api/conversations/{id}/export?format=md|json`
- The account export POSTs to `/api/export/account` and polls `/api/export/account/status`
- Use `fetch` + `URL.createObjectURL` for the file download trigger (same pattern as any file download in the browser)
- The `SettingsPage.vue` already has multiple sections — add "数据与隐私" at the end

- [ ] **Step 1: Add i18n export keys to all 6 locale files**

**zh.json** — add:
```json
"export": {
  "title": "数据导出",
  "singleConversation": "导出对话",
  "formatMarkdown": "Markdown 格式",
  "formatJson": "JSON 格式",
  "truncationNote": "（仅显示最近1000条消息）",
  "accountExport": "导出全部数据",
  "accountExportHint": "打包您的所有对话、文档元数据和记忆。API 密钥不会包含在导出中。",
  "submitted": "导出任务已提交，完成后将通知您",
  "cooldown": "距下次可导出还有 {time}",
  "downloadReady": "您的数据导出已就绪，请在25小时内下载",
  "failed": "导出失败，请稍后重试"
}
```

**en.json** — add:
```json
"export": {
  "title": "Data Export",
  "singleConversation": "Export Conversation",
  "formatMarkdown": "Markdown",
  "formatJson": "JSON",
  "truncationNote": "(showing most recent 1000 messages only)",
  "accountExport": "Export All Data",
  "accountExportHint": "Packages all your conversations, document metadata, and memories. API keys are not included.",
  "submitted": "Export started. You will be notified when ready.",
  "cooldown": "Next export available in {time}",
  "downloadReady": "Your data export is ready. Download within 25 hours.",
  "failed": "Export failed. Please try again later."
}
```

**ja.json** — add:
```json
"export": {
  "title": "データエクスポート",
  "singleConversation": "会話をエクスポート",
  "formatMarkdown": "Markdown形式",
  "formatJson": "JSON形式",
  "truncationNote": "（最新1000件のみ表示）",
  "accountExport": "全データをエクスポート",
  "accountExportHint": "すべての会話・ドキュメントメタデータ・記憶をパッケージ化します。APIキーは含まれません。",
  "submitted": "エクスポートを開始しました。完了時に通知します。",
  "cooldown": "次のエクスポートまで {time}",
  "downloadReady": "データエクスポートの準備ができました。25時間以内にダウンロードしてください。",
  "failed": "エクスポートに失敗しました。後でもう一度お試しください。"
}
```

**ko.json** — add:
```json
"export": {
  "title": "데이터 내보내기",
  "singleConversation": "대화 내보내기",
  "formatMarkdown": "Markdown 형식",
  "formatJson": "JSON 형식",
  "truncationNote": "（최근 1000개 메시지만 표시）",
  "accountExport": "전체 데이터 내보내기",
  "accountExportHint": "모든 대화, 문서 메타데이터, 기억을 패키지로 만듭니다. API 키는 포함되지 않습니다.",
  "submitted": "내보내기가 시작되었습니다. 완료 시 알림을 보내드립니다.",
  "cooldown": "다음 내보내기까지 {time}",
  "downloadReady": "데이터 내보내기가 준비되었습니다. 25시간 이내에 다운로드하세요.",
  "failed": "내보내기에 실패했습니다. 나중에 다시 시도하세요."
}
```

**fr.json** — add:
```json
"export": {
  "title": "Exportation de données",
  "singleConversation": "Exporter la conversation",
  "formatMarkdown": "Format Markdown",
  "formatJson": "Format JSON",
  "truncationNote": "(affichage des 1000 derniers messages uniquement)",
  "accountExport": "Exporter toutes les données",
  "accountExportHint": "Regroupe toutes vos conversations, métadonnées de documents et souvenirs. Les clés API ne sont pas incluses.",
  "submitted": "Exportation lancée. Vous serez notifié à la fin.",
  "cooldown": "Prochaine exportation dans {time}",
  "downloadReady": "Votre exportation est prête. Téléchargez-la dans les 25 heures.",
  "failed": "L'exportation a échoué. Veuillez réessayer plus tard."
}
```

**de.json** — add:
```json
"export": {
  "title": "Datenexport",
  "singleConversation": "Gespräch exportieren",
  "formatMarkdown": "Markdown-Format",
  "formatJson": "JSON-Format",
  "truncationNote": "(nur die letzten 1000 Nachrichten werden angezeigt)",
  "accountExport": "Alle Daten exportieren",
  "accountExportHint": "Verpackt alle Ihre Gespräche, Dokumentmetadaten und Erinnerungen. API-Schlüssel sind nicht enthalten.",
  "submitted": "Export gestartet. Sie werden benachrichtigt, wenn er abgeschlossen ist.",
  "cooldown": "Nächster Export verfügbar in {time}",
  "downloadReady": "Ihr Datenexport ist bereit. Laden Sie ihn innerhalb von 25 Stunden herunter.",
  "failed": "Export fehlgeschlagen. Bitte versuchen Sie es später erneut."
}
```

- [ ] **Step 2: Verify existing export button in ChatPage.vue (no changes needed)**

The per-conversation export button already exists in `frontend/src/pages/ChatPage.vue`:
- Lines 227–241: `<Download>` button with `exportMenuConvId` toggle
- Lines 235–240: dropdown with "Markdown (.md)" and "JSON" options
- Line 1027: already imports `exportConversation` from `@/api`
- Lines 1354–1364: `downloadExport()` handler using fetch + blob download

**No code changes needed for ChatPage.vue.** The existing implementation already calls the backend endpoint; the 1000-message cap added in Task 2 is transparent to the frontend.

If the export menu labels should use i18n instead of hardcoded English, update lines 238–239:

```vue
<!-- Before (hardcoded): -->
<button ... @click.stop="downloadExport(c.id, c.title, 'md')">Markdown (.md)</button>
<button ... @click.stop="downloadExport(c.id, c.title, 'json')">JSON</button>

<!-- After (i18n): -->
<button ... @click.stop="downloadExport(c.id, c.title, 'md')">{{ $t('export.formatMarkdown') }}</button>
<button ... @click.stop="downloadExport(c.id, c.title, 'json')">{{ $t('export.formatJson') }}</button>
```

This is optional — the labels are already clear in English.

- [ ] **Step 3: Add account export section to SettingsPage.vue**

In `frontend/src/pages/SettingsPage.vue`, add a new section at the end of the settings form (before the closing `</template>`):

```vue
<!-- Account Export Section -->
<section class="settings-section">
  <h3>{{ $t('export.title') }}</h3>
  <p class="hint">{{ $t('export.accountExportHint') }}</p>
  <button
    @click="startAccountExport"
    :disabled="exportLoading || exportCooldownSeconds > 0"
    class="btn-secondary"
  >
    {{ $t('export.accountExport') }}
  </button>
  <p v-if="exportCooldownSeconds > 0" class="hint">
    {{ $t('export.cooldown', { time: formatSeconds(exportCooldownSeconds) }) }}
  </p>
  <p v-if="exportMessage" class="hint">{{ exportMessage }}</p>
</section>
```

And in `<script setup>`:

```typescript
import { ref } from 'vue';
import axios from '@/api';

const exportLoading = ref(false);
const exportMessage = ref('');
const exportCooldownSeconds = ref(0);

async function startAccountExport() {
  exportLoading.value = true;
  exportMessage.value = '';
  try {
    await axios.post('/export/account');
    exportMessage.value = t('export.submitted');
  } catch (err: any) {
    if (err.response?.status === 429) {
      exportCooldownSeconds.value = err.response.data?.detail?.retry_after ?? 86400;
      exportMessage.value = t('export.cooldown', { time: formatSeconds(exportCooldownSeconds.value) });
    } else {
      exportMessage.value = t('export.failed');
    }
  } finally {
    exportLoading.value = false;
  }
}

function formatSeconds(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}
```

- [ ] **Step 4: Run frontend lint and type check**

```bash
cd frontend
bun run lint:fix
bun run type-check
# Expected: no errors
```

- [ ] **Step 5: Commit**

```bash
git add \
  frontend/src/pages/ChatPage.vue \
  frontend/src/pages/SettingsPage.vue \
  frontend/src/locales/zh.json \
  frontend/src/locales/en.json \
  frontend/src/locales/ja.json \
  frontend/src/locales/ko.json \
  frontend/src/locales/fr.json \
  frontend/src/locales/de.json
git commit -m "feat: add conversation export button and account export section"
```

---

## Final Verification

- [ ] **Run all backend tests**

```bash
cd backend
uv run pytest tests/ -v --tb=short
# Expected: all pass
```

- [ ] **Run pre-commit hooks**

```bash
cd /Users/hyh/code/JARVIS
pre-commit run --all-files
# Expected: all checks pass
```
