# Phase 21A: Full-Text Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a unified keyword search endpoint (`GET /api/search`) that queries conversation messages, documents, and user memories using PostgreSQL ILIKE with pg_trgm GIN index acceleration, plus a frontend search page accessible via `Cmd+K`.

**Architecture:** A new `backend/app/api/search.py` runs three concurrent ILIKE queries (messages, documents, memories) via `asyncio.gather`, merges results sorted by `created_at DESC`, and returns a unified `SearchResponse`. A new `SearchPage.vue` provides the UI with type filters and result grouping. A Alembic migration adds `pg_trgm` GIN indexes using AUTOCOMMIT mode (required for `CREATE INDEX CONCURRENTLY`).

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL pg_trgm, Vue 3, TypeScript, vue-i18n (6 locales), pytest-anyio

---

## File Map

**Create:**
- `backend/app/api/search.py` — search endpoint
- `backend/alembic/versions/c1d2e3f4a5b6_add_search_gin_indexes.py` — pg_trgm + GIN indexes
- `frontend/src/pages/SearchPage.vue` — search UI
- `backend/tests/api/test_search.py` — search tests

**Modify:**
- `backend/app/main.py` — register `search_router`
- `frontend/src/router/index.ts` — add `/search` route
- `frontend/src/pages/ChatPage.vue` — add search icon button in sidebar
- `frontend/src/App.vue` — register global `Cmd+K` / `Ctrl+K` shortcut
- `frontend/src/locales/zh.json`, `en.json`, `ja.json`, `ko.json`, `fr.json`, `de.json` — add `search.*` keys

---

## Task 1: Database Migration — pg_trgm + GIN Indexes

**Files:**
- Create: `backend/alembic/versions/c1d2e3f4a5b6_add_search_gin_indexes.py`

**Context:** `CREATE INDEX CONCURRENTLY` must run outside a transaction. Alembic wraps migrations in transactions by default. We open a fresh engine with AUTOCOMMIT isolation level, leaving Alembic's own connection untouched. The migration file must use a unique revision ID — use the literal string `c1d2e3f4a5b6` as the revision ID.

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/c1d2e3f4a5b6_add_search_gin_indexes.py
"""Add pg_trgm extension and GIN indexes for full-text search

Revision ID: c1d2e3f4a5b6
Revises: fdcf42e184ee
Create Date: 2026-03-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "fdcf42e184ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CREATE INDEX CONCURRENTLY must run outside a transaction block.
    # Use a fresh AUTOCOMMIT engine so Alembic's transaction is unaffected.
    url = op.get_context().config.get_main_option("sqlalchemy.url")
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.execute(sa.text(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_content_trgm "
            "ON messages USING gin (content gin_trgm_ops)"
        ))
        conn.execute(sa.text(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_memories_value_trgm "
            "ON user_memories USING gin (value gin_trgm_ops)"
        ))
        conn.execute(sa.text(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_documents_filename_trgm "
            "ON documents USING gin (filename gin_trgm_ops)"
        ))
    engine.dispose()


def downgrade() -> None:
    url = op.get_context().config.get_main_option("sqlalchemy.url")
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(sa.text(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_messages_content_trgm"
        ))
        conn.execute(sa.text(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_memories_value_trgm"
        ))
        conn.execute(sa.text(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_documents_filename_trgm"
        ))
    engine.dispose()
```

- [ ] **Step 2: Verify migration chain is valid**

```bash
cd backend
uv run alembic heads
# Expected: single head — c1d2e3f4a5b6
```

- [ ] **Step 3: Run the migration**

```bash
cd backend
uv run alembic upgrade head
# Expected: runs without error, creates three GIN indexes
```

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/c1d2e3f4a5b6_add_search_gin_indexes.py
git commit -m "feat: add pg_trgm GIN indexes for full-text search"
```

---

## Task 2: Backend Search API

**Files:**
- Create: `backend/app/api/search.py`
- Test: `backend/tests/api/test_search.py`

**Context:**
- `UserMemory` stores text in `.value` (not `.content`)
- `documents` uses soft-delete: `Document.is_deleted` must be filtered
- Rate limit key must be user-ID based (not IP). Look at `app/api/memory.py` for the pattern: `@limiter.limit("30/minute")` with `Request` as first param
- Workspace messages: include conversations where `Conversation.workspace_id IN (SELECT workspace_id FROM workspace_members WHERE user_id = :uid)` in addition to the user's personal conversations
- `asyncio.gather` runs the three queries concurrently

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/api/test_search.py
"""Tests for the unified search endpoint."""
import uuid

import pytest

from app.core.security import decode_access_token
from app.db.models import Conversation, Document, Message, UserMemory


def _uid(auth_client) -> uuid.UUID:
    token = auth_client.headers["Authorization"].split(" ")[1]
    return uuid.UUID(decode_access_token(token))


@pytest.mark.anyio
async def test_search_requires_auth(client):
    resp = await client.get("/api/search?q=hello")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_search_q_too_short(auth_client):
    resp = await auth_client.get("/api/search?q=ab")
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_search_q_too_long(auth_client):
    resp = await auth_client.get("/api/search?q=" + "a" * 201)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_search_invalid_type(auth_client):
    resp = await auth_client.get("/api/search?q=hello&types=foobar")
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_search_empty_results(auth_client):
    resp = await auth_client.get("/api/search?q=xyzzy_no_match")
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []
    assert body["total"] == 0


@pytest.mark.anyio
async def test_search_finds_message(auth_client, db_session):
    uid = _uid(auth_client)
    conv = Conversation(user_id=uid, title="Test Conv")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(
        conversation_id=conv.id,
        role="human",
        content="UNIQUETOKEN_XY9 searching for this",
    )
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=UNIQUETOKEN_XY9")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any(r["type"] == "message" for r in results)
    msg_result = next(r for r in results if r["type"] == "message")
    assert "UNIQUETOKEN_XY9" in msg_result["snippet"]
    assert msg_result["conversation_id"] == str(conv.id)


@pytest.mark.anyio
async def test_search_snippet_at_start(auth_client, db_session):
    """Snippet should not be prefixed with garbage when match is at pos=0."""
    uid = _uid(auth_client)
    conv = Conversation(user_id=uid, title="Snippet Test")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(
        conversation_id=conv.id,
        role="human",
        content="STARTTOKEN this text follows",
    )
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=STARTTOKEN")
    assert resp.status_code == 200
    results = resp.json()["results"]
    msg_result = next((r for r in results if r["type"] == "message"), None)
    assert msg_result is not None
    # Snippet should start with the match, not with empty/garbage prefix
    assert msg_result["snippet"].startswith("STARTTOKEN")


@pytest.mark.anyio
async def test_search_snippet_at_end(auth_client, db_session):
    """Snippet should not be suffixed with garbage when match is near end."""
    uid = _uid(auth_client)
    conv = Conversation(user_id=uid, title="End Snippet Test")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(
        conversation_id=conv.id,
        role="human",
        content="some prefix text then ENDTOKEN",
    )
    db_session.add(msg)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=ENDTOKEN")
    assert resp.status_code == 200
    results = resp.json()["results"]
    msg_result = next((r for r in results if r["type"] == "message"), None)
    assert msg_result is not None
    assert "ENDTOKEN" in msg_result["snippet"]
    # Snippet should end cleanly (not with None or extra chars)
    assert isinstance(msg_result["snippet"], str)


@pytest.mark.anyio
async def test_search_finds_document(auth_client, db_session):
    uid = _uid(auth_client)
    doc = Document(
        user_id=uid,
        filename="UNIQUEDOC_ABC.pdf",
        file_type="pdf",
        file_size_bytes=100,
        qdrant_collection=f"user_{uid}",
        minio_object_key=f"{uid}/test.pdf",
        is_deleted=False,
    )
    db_session.add(doc)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=UNIQUEDOC_ABC")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any(r["type"] == "document" for r in results)


@pytest.mark.anyio
async def test_search_excludes_soft_deleted_document(auth_client, db_session):
    uid = _uid(auth_client)
    doc = Document(
        user_id=uid,
        filename="DELETED_DOC_ZZZ.pdf",
        file_type="pdf",
        file_size_bytes=100,
        qdrant_collection=f"user_{uid}",
        minio_object_key=f"{uid}/deleted.pdf",
        is_deleted=True,  # soft deleted
    )
    db_session.add(doc)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=DELETED_DOC_ZZZ")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert not any(r["type"] == "document" for r in results)


@pytest.mark.anyio
async def test_search_finds_memory(auth_client, db_session):
    uid = _uid(auth_client)
    mem = UserMemory(
        user_id=uid,
        key="test_pref",
        value="UNIQMEMORY_Q7 user prefers dark mode",
        category="preference",
    )
    db_session.add(mem)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=UNIQMEMORY_Q7")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any(r["type"] == "memory" for r in results)


@pytest.mark.anyio
async def test_search_types_filter(auth_client, db_session):
    """types=messages should exclude documents and memories."""
    uid = _uid(auth_client)
    conv = Conversation(user_id=uid, title="Filter Test")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(
        conversation_id=conv.id, role="human", content="FILTERTEST_TOKEN123"
    )
    db_session.add(msg)
    doc = Document(
        user_id=uid,
        filename="FILTERTEST_TOKEN123.pdf",
        file_type="pdf",
        file_size_bytes=100,
        qdrant_collection=f"user_{uid}",
        minio_object_key=f"{uid}/f.pdf",
        is_deleted=False,
    )
    db_session.add(doc)
    await db_session.commit()

    resp = await auth_client.get("/api/search?q=FILTERTEST_TOKEN123&types=messages")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert all(r["type"] == "message" for r in results)
    assert len(results) >= 1


@pytest.mark.anyio
async def test_search_user_isolation(auth_client, second_user_auth_headers, client, db_session):
    """User A must not see User B's messages."""
    from app.db.models import Conversation as Conv, Message as Msg
    token2 = second_user_auth_headers["Authorization"].split(" ")[1]
    uid2 = uuid.UUID(decode_access_token(token2))

    conv2 = Conv(user_id=uid2, title="User2 Conv")
    db_session.add(conv2)
    await db_session.flush()
    msg2 = Msg(
        conversation_id=conv2.id,
        role="human",
        content="ISOLATEDTOKEN_USER2_ONLY",
    )
    db_session.add(msg2)
    await db_session.commit()

    # User 1 should not find user 2's message
    resp = await auth_client.get("/api/search?q=ISOLATEDTOKEN_USER2_ONLY")
    assert resp.status_code == 200
    assert resp.json()["results"] == []
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend
uv run pytest tests/api/test_search.py -v 2>&1 | head -30
# Expected: ERROR — no module named app.api.search (ImportError)
```

- [ ] **Step 3: Implement the search endpoint**

```python
# backend/app/api/search.py
"""Unified keyword search across messages, documents, and user memories."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.db.models import Conversation, Document, Message, User, UserMemory, WorkspaceMember
from app.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])

_SNIPPET_RADIUS = 80  # characters each side of the match


def _make_snippet(text_val: str, keyword: str) -> str:
    """Extract a snippet around the first case-insensitive match of keyword."""
    lower_text = text_val.lower()
    lower_kw = keyword.lower()
    pos = lower_text.find(lower_kw)
    if pos == -1:
        return text_val[:_SNIPPET_RADIUS * 2]
    start = max(0, pos - _SNIPPET_RADIUS)
    end = pos + len(keyword) + _SNIPPET_RADIUS
    return text_val[start:end]


class SearchResultItem(BaseModel):
    type: Literal["message", "document", "memory"]
    id: uuid.UUID
    snippet: str
    created_at: str
    # message-specific
    conversation_id: uuid.UUID | None = None
    conversation_title: str | None = None
    # document-specific
    filename: str | None = None
    file_type: str | None = None


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total: int


@router.get("", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search(
    request: Request,
    q: str = Query(..., min_length=3, max_length=200),
    types: str = Query(default="messages,documents,memories"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search messages, documents, and memories by keyword."""
    # Validate types parameter
    valid_types = {"messages", "documents", "memories"}
    requested = {t.strip() for t in types.split(",") if t.strip()}
    invalid = requested - valid_types
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid types: {', '.join(sorted(invalid))}. Valid: {', '.join(sorted(valid_types))}",
        )

    pattern = f"%{q}%"
    uid = user.id

    tasks = []
    if "messages" in requested:
        tasks.append(_search_messages(db, uid, pattern, q, date_from, date_to, limit))
    else:
        tasks.append(_empty())
    if "documents" in requested:
        tasks.append(_search_documents(db, uid, pattern, q, date_from, date_to, limit))
    else:
        tasks.append(_empty())
    if "memories" in requested:
        tasks.append(_search_memories(db, uid, pattern, q, date_from, date_to, limit))
    else:
        tasks.append(_empty())

    msg_results, doc_results, mem_results = await asyncio.gather(*tasks)

    all_results = msg_results + doc_results + mem_results
    all_results.sort(key=lambda r: r.created_at, reverse=True)

    return SearchResponse(results=all_results, total=len(all_results))


async def _empty() -> list[SearchResultItem]:
    return []


async def _search_messages(
    db: AsyncSession,
    uid: uuid.UUID,
    pattern: str,
    keyword: str,
    date_from: date | None,
    date_to: date | None,
    limit: int,
) -> list[SearchResultItem]:
    # Personal conversations + workspace conversations user is a member of
    workspace_subq = (
        select(WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == uid)
        .scalar_subquery()
    )
    stmt = (
        select(Message, Conversation.title, Conversation.id.label("conv_id"))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.content.ilike(pattern),
            Message.role.in_(["human", "ai"]),
            (
                (Conversation.user_id == uid)
                | (Conversation.workspace_id.in_(workspace_subq))
            ),
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    if date_from:
        stmt = stmt.where(Message.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Message.created_at <= date_to)

    rows = await db.execute(stmt)
    results = []
    for row in rows:
        msg, conv_title, conv_id = row
        results.append(
            SearchResultItem(
                type="message",
                id=msg.id,
                snippet=_make_snippet(msg.content, keyword),
                created_at=msg.created_at.isoformat(),
                conversation_id=conv_id,
                conversation_title=conv_title,
            )
        )
    return results


async def _search_documents(
    db: AsyncSession,
    uid: uuid.UUID,
    pattern: str,
    keyword: str,
    date_from: date | None,
    date_to: date | None,
    limit: int,
) -> list[SearchResultItem]:
    workspace_subq = (
        select(WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == uid)
        .scalar_subquery()
    )
    stmt = (
        select(Document)
        .where(
            Document.filename.ilike(pattern),
            Document.is_deleted.is_(False),
            (
                (Document.user_id == uid) & (Document.workspace_id.is_(None))
                | (Document.workspace_id.in_(workspace_subq))
            ),
        )
        .order_by(Document.created_at.desc())
        .limit(limit)
    )
    if date_from:
        stmt = stmt.where(Document.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Document.created_at <= date_to)

    rows = await db.scalars(stmt)
    return [
        SearchResultItem(
            type="document",
            id=doc.id,
            snippet=_make_snippet(doc.filename, keyword),
            created_at=doc.created_at.isoformat(),
            filename=doc.filename,
            file_type=doc.file_type,
        )
        for doc in rows.all()
    ]


async def _search_memories(
    db: AsyncSession,
    uid: uuid.UUID,
    pattern: str,
    keyword: str,
    date_from: date | None,
    date_to: date | None,
    limit: int,
) -> list[SearchResultItem]:
    # UserMemory.value is the text field (not .content)
    stmt = (
        select(UserMemory)
        .where(
            UserMemory.user_id == uid,
            UserMemory.value.ilike(pattern),
        )
        .order_by(UserMemory.created_at.desc())
        .limit(limit)
    )
    if date_from:
        stmt = stmt.where(UserMemory.created_at >= date_from)
    if date_to:
        stmt = stmt.where(UserMemory.created_at <= date_to)

    rows = await db.scalars(stmt)
    return [
        SearchResultItem(
            type="memory",
            id=mem.id,
            snippet=_make_snippet(mem.value, keyword),
            created_at=mem.created_at.isoformat(),
        )
        for mem in rows.all()
    ]
```

- [ ] **Step 4: Register the router in main.py**

In `backend/app/main.py`, add after the last router import:

```python
from app.api.search import router as search_router
```

And in the `app.include_router(...)` section (keep alphabetical order), add:

```python
app.include_router(search_router)
```

- [ ] **Step 5: Run import check**

```bash
cd backend
uv run pytest --collect-only -q 2>&1 | tail -5
# Expected: no errors, all tests collected
```

- [ ] **Step 6: Run the search tests**

```bash
cd backend
uv run pytest tests/api/test_search.py -v
# Expected: all tests PASS
```

- [ ] **Step 7: Run lint and type check**

```bash
cd backend
uv run ruff check --fix && uv run ruff format && uv run mypy app
# Expected: no errors
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/search.py backend/app/main.py backend/tests/api/test_search.py
git commit -m "feat: add unified search endpoint across messages, documents, memories"
```

---

## Task 3: Frontend Search Page

**Files:**
- Create: `frontend/src/pages/SearchPage.vue`
- Modify: `frontend/src/router/index.ts` — add `/search` route
- Modify: `frontend/src/pages/ChatPage.vue` — add search icon button in sidebar
- Modify: `frontend/src/App.vue` — register global `Cmd+K` / `Ctrl+K`
- Modify: `frontend/src/locales/zh.json`, `en.json`, `ja.json`, `ko.json`, `fr.json`, `de.json`

**Context:**
- Vue Router uses `createRouter` with `createWebHistory`. All page components are lazy-loaded with `() => import(...)`.
- i18n: keys go under a `search` namespace. The existing pattern is a flat JSON file with nested objects.
- There is no dedicated search store. The page component manages its own state with `ref()` / `computed()`.
- The `api` client is an Axios instance at `src/api/index.ts` (or similar). Check `src/api/` for the pattern.

- [ ] **Step 1: Add i18n keys to all 6 locale files**

For each locale file, add a `"search"` key at the top level. Translations below:

**zh.json** — add inside the root object:
```json
"search": {
  "title": "搜索",
  "placeholder": "搜索对话、文档和记忆（至少3个字符）",
  "minLength": "请至少输入3个字符",
  "noResults": "未找到相关内容",
  "resultCount": "共 {count} 条结果",
  "types": {
    "all": "全部",
    "messages": "对话消息",
    "documents": "文档",
    "memories": "记忆"
  },
  "labels": {
    "conversation": "来自对话：{title}",
    "document": "文档：{filename}",
    "memory": "记忆"
  }
}
```

**en.json** — add:
```json
"search": {
  "title": "Search",
  "placeholder": "Search conversations, documents, and memories (min 3 chars)",
  "minLength": "Please enter at least 3 characters",
  "noResults": "No results found",
  "resultCount": "{count} result(s) found",
  "types": {
    "all": "All",
    "messages": "Messages",
    "documents": "Documents",
    "memories": "Memories"
  },
  "labels": {
    "conversation": "From: {title}",
    "document": "Document: {filename}",
    "memory": "Memory"
  }
}
```

**ja.json** — add:
```json
"search": {
  "title": "検索",
  "placeholder": "会話・ドキュメント・記憶を検索（3文字以上）",
  "minLength": "3文字以上入力してください",
  "noResults": "結果が見つかりません",
  "resultCount": "{count}件の結果",
  "types": {
    "all": "すべて",
    "messages": "メッセージ",
    "documents": "ドキュメント",
    "memories": "記憶"
  },
  "labels": {
    "conversation": "会話：{title}",
    "document": "ドキュメント：{filename}",
    "memory": "記憶"
  }
}
```

**ko.json** — add:
```json
"search": {
  "title": "검색",
  "placeholder": "대화, 문서, 기억 검색 (최소 3자)",
  "minLength": "3자 이상 입력하세요",
  "noResults": "결과를 찾을 수 없습니다",
  "resultCount": "{count}개 결과",
  "types": {
    "all": "전체",
    "messages": "메시지",
    "documents": "문서",
    "memories": "기억"
  },
  "labels": {
    "conversation": "대화: {title}",
    "document": "문서: {filename}",
    "memory": "기억"
  }
}
```

**fr.json** — add:
```json
"search": {
  "title": "Recherche",
  "placeholder": "Rechercher conversations, documents et mémoires (min 3 car.)",
  "minLength": "Veuillez saisir au moins 3 caractères",
  "noResults": "Aucun résultat trouvé",
  "resultCount": "{count} résultat(s)",
  "types": {
    "all": "Tout",
    "messages": "Messages",
    "documents": "Documents",
    "memories": "Mémoires"
  },
  "labels": {
    "conversation": "De : {title}",
    "document": "Document : {filename}",
    "memory": "Mémoire"
  }
}
```

**de.json** — add:
```json
"search": {
  "title": "Suche",
  "placeholder": "Gespräche, Dokumente und Erinnerungen suchen (min. 3 Zeichen)",
  "minLength": "Bitte mindestens 3 Zeichen eingeben",
  "noResults": "Keine Ergebnisse gefunden",
  "resultCount": "{count} Ergebnis(se)",
  "types": {
    "all": "Alle",
    "messages": "Nachrichten",
    "documents": "Dokumente",
    "memories": "Erinnerungen"
  },
  "labels": {
    "conversation": "Aus: {title}",
    "document": "Dokument: {filename}",
    "memory": "Erinnerung"
  }
}
```

- [ ] **Step 2: Add `/search` route in router**

In `frontend/src/router/index.ts`, add inside the `routes` array (before the wildcard `/:pathMatch` route):

```typescript
{ path: "/search", component: () => import("@/pages/SearchPage.vue"), meta: { requiresAuth: true } },
```

- [ ] **Step 3: Create SearchPage.vue**

```vue
<!-- frontend/src/pages/SearchPage.vue -->
<script setup lang="ts">
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import axios from "@/api";

const { t } = useI18n();
const router = useRouter();

interface SearchResult {
  type: "message" | "document" | "memory";
  id: string;
  snippet: string;
  created_at: string;
  conversation_id?: string;
  conversation_title?: string;
  filename?: string;
  file_type?: string;
}

interface SearchResponse {
  results: SearchResult[];
  total: number;
}

const query = ref("");
const selectedTypes = ref<string>("messages,documents,memories");
const results = ref<SearchResult[]>([]);
const total = ref(0);
const loading = ref(false);
const searched = ref(false);

const typeOptions = [
  { value: "messages,documents,memories", label: computed(() => t("search.types.all")) },
  { value: "messages", label: computed(() => t("search.types.messages")) },
  { value: "documents", label: computed(() => t("search.types.documents")) },
  { value: "memories", label: computed(() => t("search.types.memories")) },
];

const canSearch = computed(() => query.value.trim().length >= 3);

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

function onInput() {
  if (debounceTimer) clearTimeout(debounceTimer);
  if (!canSearch.value) {
    results.value = [];
    searched.value = false;
    return;
  }
  debounceTimer = setTimeout(doSearch, 300);
}

async function doSearch() {
  loading.value = true;
  searched.value = true;
  try {
    const resp = await axios.get<SearchResponse>("/search", {
      params: { q: query.value.trim(), types: selectedTypes.value, limit: 20 },
    });
    results.value = resp.data.results;
    total.value = resp.data.total;
  } catch {
    results.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

function highlightSnippet(snippet: string, kw: string): string {
  const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return snippet.replace(new RegExp(escaped, "gi"), (m) => `<mark>${m}</mark>`);
}

function navigate(result: SearchResult) {
  if (result.type === "message" && result.conversation_id) {
    router.push({ path: "/", query: { conversation_id: result.conversation_id } });
  } else if (result.type === "document") {
    router.push("/documents");
  } else if (result.type === "memory") {
    router.push("/settings");
  }
}
</script>

<template>
  <div class="search-page">
    <h1>{{ t("search.title") }}</h1>

    <div class="search-bar">
      <input
        v-model="query"
        type="text"
        :placeholder="t('search.placeholder')"
        @input="onInput"
        autofocus
      />
      <select v-model="selectedTypes" @change="canSearch && doSearch()">
        <option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
      </select>
    </div>

    <p v-if="query.length > 0 && query.length < 3" class="hint">
      {{ t("search.minLength") }}
    </p>

    <div v-if="loading" class="loading">...</div>

    <div v-else-if="searched && results.length === 0" class="no-results">
      {{ t("search.noResults") }}
    </div>

    <div v-else-if="results.length > 0">
      <p class="result-count">{{ t("search.resultCount", { count: total }) }}</p>
      <ul class="result-list">
        <li
          v-for="result in results"
          :key="result.id"
          class="result-item"
          @click="navigate(result)"
        >
          <div class="result-meta">
            <span class="result-type">{{ t(`search.types.${result.type === 'message' ? 'messages' : result.type === 'document' ? 'documents' : 'memories'}`) }}</span>
            <span v-if="result.type === 'message'" class="result-source">
              {{ t("search.labels.conversation", { title: result.conversation_title }) }}
            </span>
            <span v-else-if="result.type === 'document'" class="result-source">
              {{ t("search.labels.document", { filename: result.filename }) }}
            </span>
            <span v-else class="result-source">{{ t("search.labels.memory") }}</span>
          </div>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <p class="snippet" v-html="highlightSnippet(result.snippet, query)" />
          <span class="result-date">{{ new Date(result.created_at).toLocaleDateString() }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.search-page { max-width: 800px; margin: 0 auto; padding: 24px; }
.search-bar { display: flex; gap: 8px; margin-bottom: 16px; }
.search-bar input { flex: 1; padding: 8px 12px; font-size: 16px; }
.search-bar select { padding: 8px; }
.hint, .no-results { color: #888; }
.result-count { font-size: 13px; color: #888; margin-bottom: 12px; }
.result-list { list-style: none; padding: 0; margin: 0; }
.result-item { padding: 12px; border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 8px; cursor: pointer; }
.result-item:hover { background: #f5f5f5; }
.result-meta { display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }
.result-type { font-size: 11px; background: #e8f0fe; color: #1a73e8; padding: 2px 6px; border-radius: 4px; }
.result-source { font-size: 12px; color: #666; }
.snippet { margin: 4px 0; font-size: 14px; }
.snippet :deep(mark) { background: #fff176; padding: 0 2px; }
.result-date { font-size: 11px; color: #aaa; }
</style>
```

- [ ] **Step 4: Add search button in ChatPage.vue sidebar**

Find the sidebar section in `frontend/src/pages/ChatPage.vue` where the conversation list header is. Add a search icon button that navigates to `/search`. Look for the `<aside>` or sidebar container and add near the top:

```vue
<button @click="$router.push('/search')" :title="$t('search.title')" class="search-btn">
  🔍
</button>
```

The exact location depends on the current sidebar markup — place it in the sidebar header, alongside any existing action buttons.

- [ ] **Step 5: Add global Cmd+K shortcut in App.vue**

In `frontend/src/App.vue`, inside the `<script setup>` block, add:

```typescript
import { onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

function onKeyDown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") {
    e.preventDefault();
    router.push("/search");
  }
}

onMounted(() => window.addEventListener("keydown", onKeyDown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeyDown));
```

If `App.vue` already has a `<script setup>` block with imports/router usage, add the above inside it.

- [ ] **Step 6: Run frontend lint and type check**

```bash
cd frontend
bun run lint:fix
bun run type-check
# Expected: no errors
```

- [ ] **Step 7: Commit**

```bash
git add \
  frontend/src/pages/SearchPage.vue \
  frontend/src/router/index.ts \
  frontend/src/pages/ChatPage.vue \
  frontend/src/App.vue \
  frontend/src/locales/zh.json \
  frontend/src/locales/en.json \
  frontend/src/locales/ja.json \
  frontend/src/locales/ko.json \
  frontend/src/locales/fr.json \
  frontend/src/locales/de.json
git commit -m "feat: add search page with Cmd+K shortcut and i18n"
```

---

## Final Verification

- [ ] **Run all backend tests**

```bash
cd backend
uv run pytest tests/ -v --tb=short
# Expected: all pass, no regression
```

- [ ] **Run pre-commit hooks**

```bash
cd /Users/hyh/code/JARVIS
pre-commit run --all-files
# Expected: all checks pass
```
