# Phase 21: Search & Export Design Spec

> Generated: 2026-03-26
> Status: Draft (v3 — post second spec-review fixes)
> Scope: Full-text search across conversations/documents/memories + single-conversation and full-account data export

---

## Background

JARVIS has completed Phases 1-20, delivering a full-featured AI assistant platform with RAG, multi-LLM support, multi-tenancy, workflow studio, voice, monitoring, and comprehensive security hardening. Phase 21 targets two user-experience gaps that become increasingly painful as users accumulate data:

1. **No way to find past conversations** — users must scroll through conversation history to locate specific content
2. **No way to export data** — users cannot back up, migrate, or share their conversation history and knowledge base

---

## Sub-system 1: Full-Text Search

### Goal

A unified search endpoint that queries `messages.content`, `documents.filename`, and `user_memories.value` using PostgreSQL ILIKE with `pg_trgm` GIN index acceleration. Results are returned in a single ranked list with contextual snippets.

> **Model note**: `UserMemory` stores text in the `value` column (not `content`). All references to memory search use `user_memories.value`.

### Architecture

**New file**: `backend/app/api/search.py`
**New migration**: Add `pg_trgm` extension + GIN indexes
**New frontend page**: `frontend/src/pages/SearchPage.vue`
**Router addition**: `frontend/src/router/index.ts`

### Backend API

#### `GET /api/search`

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string (**3**–200 chars) | required | Search keyword. Minimum 3 chars required for `pg_trgm` index to be used; shorter patterns fall back to sequential scan. |
| `types` | comma-separated enum: `messages`, `documents`, `memories` | all three | Scope of search. Invalid values → 422. |
| `date_from` | ISO 8601 date | none | Filter results created on or after this date |
| `date_to` | ISO 8601 date | none | Filter results created on or before this date |
| `limit` | int (1–50) | 20 | Max results per type |

**Authentication**: Required (JWT / PAT). Users only see their own data.

**Rate limit**: 30 requests/minute per user. Key function: **user ID extracted from JWT/PAT** (not IP address), so PAT users are correctly throttled by identity.

**Response schema** (`SearchResponse`):

```json
{
  "results": [
    {
      "type": "message",
      "id": "uuid",
      "snippet": "...context around the match (80 chars each side)...",
      "conversation_id": "uuid",
      "conversation_title": "string",
      "created_at": "ISO 8601"
    },
    {
      "type": "document",
      "id": "uuid",
      "snippet": "filename match",
      "filename": "string",
      "file_type": "string",
      "created_at": "ISO 8601"
    },
    {
      "type": "memory",
      "id": "uuid",
      "snippet": "...memory content fragment...",
      "created_at": "ISO 8601"
    }
  ],
  "total": 42
}
```

**Implementation**:
- Three `SELECT ... WHERE column ILIKE :pattern LIMIT :limit` queries run concurrently via `asyncio.gather`
- Pattern: `%{q}%` (parameterized, prevents SQL injection)
- Snippet extraction: locate first case-insensitive match position `pos`; slice `content[max(0, pos-80) : pos+80+len(q)]`. Handles boundary conditions: when `pos < 80` the prefix is simply truncated to start-of-string; when match is near end, suffix is truncated to end-of-string.
- Results merged and sorted by `created_at DESC`
- Soft-deleted documents (`documents.is_deleted = true`) are **excluded** from results
- Memory queries use `user_memories.value` (not `content` — the actual column name in the `UserMemory` model)
- `total` = `len(results)` — the count of items actually returned across all queried types (≤ `limit × number_of_types`). Does **not** represent the unfettered match count. This is explicitly documented in the API; a pagination-aware count is out of scope for Phase 21.

**Workspace scope for messages**: Include messages from conversations where:
- `conversation.user_id = :uid` (personal), **OR**
- `conversation.workspace_id IN (SELECT workspace_id FROM workspace_members WHERE user_id = :uid)` (workspace member)

**Workspace scope for documents**: Include documents where:
- `document.user_id = :uid AND document.workspace_id IS NULL` (personal), **OR**
- `document.workspace_id IN (SELECT workspace_id FROM workspace_members WHERE user_id = :uid)`

#### Database Migration

New Alembic migration (`041_add_search_gin_indexes.py`).

`CREATE INDEX CONCURRENTLY` **cannot run inside a transaction**. Alembic wraps migrations in transactions by default; mutating the Alembic-managed connection's isolation level corrupts migration state tracking. The safe pattern is to **open a fresh engine** with `AUTOCOMMIT` isolation, leaving the Alembic connection untouched:

```python
# In the migration file
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    # CREATE INDEX CONCURRENTLY must run outside a transaction.
    # Use a fresh AUTOCOMMIT engine so Alembic's own transaction is unaffected.
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
            "ON user_memories USING gin (value gin_trgm_ops)"  # column is 'value', not 'content'
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
        conn.execute(sa.text("DROP INDEX CONCURRENTLY IF EXISTS ix_messages_content_trgm"))
        conn.execute(sa.text("DROP INDEX CONCURRENTLY IF EXISTS ix_memories_value_trgm"))
        conn.execute(sa.text("DROP INDEX CONCURRENTLY IF EXISTS ix_documents_filename_trgm"))
    engine.dispose()
```

### Frontend

#### New Route and Page

- Route: `/search` added to `frontend/src/router/index.ts` (requires auth)
- Page: `SearchPage.vue` — search input, type filter chips (messages / documents / memories), date range pickers, result list grouped by type
- Results show snippet with keyword highlighted (`<mark>` tag)
- Clicking a `message` result navigates to `/` and selects the corresponding conversation
- Clicking a `document` result navigates to `/documents`
- Clicking a `memory` result navigates to `/settings` (memories section)

#### Sidebar Entry

- `ChatPage.vue` sidebar: add search icon button above conversation list
- Keyboard shortcut: `Ctrl+K` (Windows/Linux) / `Cmd+K` (macOS) opens search page
- Shortcut registered as a global `keydown` listener in `App.vue`

#### i18n Keys

All 6 locale files (`zh.json`, `en.json`, `ja.json`, `ko.json`, `fr.json`, `de.json`) receive new `search` namespace:

```json
"search": {
  "title": "搜索",
  "placeholder": "搜索对话、文档和记忆（至少3个字符）",
  "types": {
    "messages": "对话消息",
    "documents": "文档",
    "memories": "记忆"
  },
  "noResults": "未找到相关内容",
  "resultCount": "共 {count} 条结果",
  "minLength": "请至少输入3个字符",
  "snippet": {
    "conversation": "来自对话：{title}",
    "document": "文档：{filename}",
    "memory": "记忆"
  }
}
```

### Error Handling

- `q` shorter than 3 chars or longer than 200 chars → 422 with validation message
- `types` contains an invalid value → 422
- Database unavailable → 503
- No results → 200 with empty `results` array (not 404)

---

## Sub-system 2: Data Export

### Goal

Two export modes:
1. **Single conversation export**: Synchronous download of one conversation as Markdown or JSON (capped at 1000 messages)
2. **Full account export**: Asynchronous background job that packages all user data into a ZIP stored in MinIO, with a time-limited download link delivered via the notification system

### Architecture

**New file**: `backend/app/api/export.py` — contains the **account export endpoints only** (`POST /api/export/account`, `GET /api/export/account/status`).

**Modified file**: `backend/app/api/conversations.py` — the existing `GET /api/conversations/{conv_id}/export` endpoint is **extended** (not replaced) to add the 1000-message cap and `truncated` field. A new route in `export.py` is **not** added for per-conversation export to avoid creating a duplicate endpoint with an overlapping URL pattern.

**New ARQ task**: `export_account` in `backend/app/worker.py`

**Frontend changes**: `ChatPage.vue` (per-conversation export button), `SettingsPage.vue` (account export section)

**MinIO bucket policy**: The existing MinIO bucket is **private** (no public access). All access goes through either the backend API (streaming) or MinIO presigned URLs. This is an existing constraint; no change required.

### Backend API

#### Single Conversation Export (extend existing endpoint)

**`GET /api/conversations/{conv_id}/export`** — **existing endpoint in `conversations.py`**, extended with:

| Change | Detail |
|--------|--------|
| Add `format=markdown` alias | Currently accepts `md|json|txt`; add `markdown` as alias for `md` for clarity (backwards-compatible) |
| Add 1000-message cap | Query `ORDER BY created_at DESC LIMIT 1000` then reverse; set `truncated=True` when total > 1000 |
| Add `truncated` to JSON output | New field in the JSON response body |
| Add truncation note to Markdown | Append `(showing most recent 1000 of {total} messages)` to the metadata header when truncated |

**Authorization**: Existing logic unchanged — user must own conversation, or valid share token.

**Message cap**: Exports are limited to the **most recent 1000 messages**. For full history, use the account export.

**Response**: `StreamingResponse` with `Content-Disposition: attachment` header — existing behavior unchanged.

**Rate limit**: Existing 60/minute kept (no change needed; export size is now capped).

**Markdown format** (concrete template):

```markdown
# {conversation title}

> Exported: {YYYY-MM-DD HH:MM UTC}
> Model: {model_name}
> Messages: {count}{truncation_note}

---

**用户** · {YYYY-MM-DD HH:MM}
{message content}

**助手** · {YYYY-MM-DD HH:MM}
{message content}
```

Where `{truncation_note}` is either empty or ` (showing most recent 1000 of {total} messages)`.

**JSON format**:

```json
{
  "id": "uuid",
  "title": "string",
  "model_name": "string",
  "created_at": "ISO 8601",
  "exported_at": "ISO 8601",
  "truncated": false,
  "messages": [
    {
      "id": "uuid",
      "role": "human|ai",
      "content": "string",
      "created_at": "ISO 8601"
    }
  ]
}
```

#### Full Account Export

**`POST /api/export/account`**

Enqueues an ARQ background job. The `user_id` used for the job is extracted **server-side from the authenticated JWT/PAT** at enqueue time — it is never taken from the request body. This prevents tampering even if the ARQ Redis queue were accessible.

Returns immediately:

```json
{ "message": "Export started. You will be notified when ready." }
```

Note: No `task_id` is returned. Status is keyed by `user_id` since only one export per user can be in flight (enforced by the 24h cooldown). Returning a `task_id` would be misleading since the status endpoint does not accept one.

**Rate limit**: 1 request per 24 hours per user. Enforced via Redis key `export_cooldown:{user_id}` (TTL 86400s) using an atomic `SET NX` check. The cooldown check and enqueue happen atomically to prevent TOCTOU race conditions.

If within cooldown: returns 429 with:
```json
{
  "detail": "Export already requested. Try again in {seconds} seconds.",
  "retry_after": 12345
}
```

**`GET /api/export/account/status`**

```json
{
  "status": "pending|running|done|failed",
  "created_at": "ISO 8601",
  "download_url": "https://... (present only when status=done)",
  "expires_at": "ISO 8601 (present only when status=done)"
}
```

Status stored in Redis key `export_status:{user_id}` (TTL **25 hours**).

**Known behavior**: If the Redis key expires (after 25 hours) before the user checks status, the status is lost. The presigned URL in the notification (sent when export completes) remains valid for **25 hours** from completion. Once both the Redis key and notification link expire, there is no recovery path — the user must re-trigger the export. This is **explicitly acceptable** behavior for Phase 21; a DB-backed status table is out of scope.

**Presigned URL TTL**: **25 hours** (matching the Redis status TTL and the cleanup window), avoiding the scenario where status says "done" but the URL has already expired.

#### ARQ Worker Task: `export_account`

The worker receives `{"user_id": "uuid"}` from the ARQ queue (server-side injected at enqueue).

Steps:

1. **Conversations + messages**: Query all user's conversations (including workspace conversations where user is a member); for each, serialize up to 10,000 messages to a Markdown file under `conversations/` in the ZIP. Conversations are named `{YYYY-MM-DD}_{sanitized-title}.md`.
2. **Documents metadata**: Query non-deleted `documents` rows; serialize to `documents.json` (no raw file content).
3. **Memories**: Query `user_memories`; serialize to `memories.json`.
4. **Settings**: Query `user_settings`; serialize to `settings.json`. `api_keys` field replaced with `"[REDACTED]"`. All other user-controlled settings retained.
5. **Build ZIP**: Use `tempfile.NamedTemporaryFile` (not `io.BytesIO`) to avoid memory pressure on large accounts. Stream `zipfile.ZipFile` writes to the temp file.
6. **Upload to MinIO**: `asyncio.to_thread(minio_client.put_object, ...)`, object key `exports/{user_id}/{task_id}.zip`. Use MinIO's streaming upload with the temp file handle.
7. **Presign**: Generate a **25-hour** presigned download URL.
8. **Notify**: Insert `Notification` row (type `account_export_ready`, body includes the download URL and expiry time).
9. **Update Redis**: Set `export_status:{user_id}` = `{status: "done", download_url: ..., expires_at: ..., created_at: ...}` with TTL 25 hours.
10. **Cleanup temp file**: Delete the temp file.

**Error handling**: On any step failure, set Redis `export_status:{user_id}` = `{status: "failed"}`, insert `Notification` (type `account_export_failed`), log exception with `logger.exception`.

#### Cleanup Cron: `cleanup_expired_exports`

**Schedule**: Runs hourly (`0 * * * *`), registered in ARQ's `cron_jobs` list in `worker.py`.

**Discovery mechanism**: The cron task queries a Redis Set `export_pending_cleanup` — when a new export is enqueued, its MinIO object key is added to this set with a score of `enqueue_timestamp + 25*3600` (using a Redis Sorted Set for TTL-based ordering). The cron task:
1. `ZRANGEBYSCORE export_pending_cleanup 0 {now}` — retrieve all keys whose cleanup time has passed
2. For each key: delete the MinIO object (`minio_client.remove_object`)
3. `ZREM export_pending_cleanup {key}` — remove from the set

This avoids enumerating MinIO objects and handles partial failures gracefully (the key remains in the set and is retried next hour if MinIO delete fails).

### Frontend

#### Per-Conversation Export

`ChatPage.vue` three-dot conversation header menu: new "导出对话" item. Sub-choice: Markdown or JSON. On selection, triggers a `fetch` to `GET /api/export/conversations/{id}?format=markdown|json` and uses `URL.createObjectURL` for client-side download (no page navigation).

#### Account Export (`SettingsPage.vue`)

New "数据与隐私" section:
- "导出全部数据" button with description: "打包您的所有对话、文档元数据和记忆（不含 API 密钥）"
- On click → `POST /api/export/account` → toast "导出任务已提交，完成后将通知您"
- If 429 (cooldown active): show "距下次可导出还有 {time}" (parse `retry_after` from response)
- Completion: Notification in notification center with download link, shows expiry time

#### i18n Keys

```json
"export": {
  "title": "数据导出",
  "singleConversation": "导出对话",
  "formatMarkdown": "Markdown 格式",
  "formatJson": "JSON 格式",
  "truncated": "（已截断，仅显示最近 1000 条消息）",
  "accountExport": "导出全部数据",
  "accountExportHint": "将打包您的所有对话、文档元数据和记忆，API 密钥不会包含在导出中",
  "submitted": "导出任务已提交，完成后将通知您",
  "cooldown": "距下次可导出还有 {time}",
  "downloadReady": "您的数据导出已就绪，请在25小时内下载",
  "failed": "导出失败，请稍后重试"
}
```

### Security Constraints

- API keys, password hashes, and Fernet-encrypted values are **never** exported
- MinIO bucket is **private**; only presigned URLs grant temporary access
- Presigned URLs expire in **25 hours** and the underlying object is deleted after 25 hours
- `user_id` for the export task is extracted server-side from the authenticated session at enqueue time, never from client input
- Atomic Redis `SET NX` prevents TOCTOU race condition on the 24h cooldown check

---

## File Map

### New Files

| File | Purpose |
|------|---------|
| `backend/app/api/search.py` | Search endpoint |
| `backend/app/api/export.py` | Account export endpoints only (POST /api/export/account + GET /api/export/account/status) |
| `backend/alembic/versions/041_add_search_gin_indexes.py` | pg_trgm extension + GIN indexes (AUTOCOMMIT mode) |
| `frontend/src/pages/SearchPage.vue` | Search UI page |
| `backend/tests/api/test_search.py` | Search endpoint tests |
| `backend/tests/api/test_export.py` | Export endpoint tests |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/main.py` | Register `search_router` and `export_router` |
| `backend/app/worker.py` | Add `export_account` ARQ task + `cleanup_expired_exports` hourly cron |
| `backend/app/api/conversations.py` | Extend existing `GET /{conv_id}/export` with 1000-message cap + `truncated` field |
| `frontend/src/router/index.ts` | Add `/search` route |
| `frontend/src/pages/ChatPage.vue` | Search shortcut (`Cmd+K`) + conversation export button |
| `frontend/src/pages/SettingsPage.vue` | "数据与隐私" section with account export |
| `frontend/src/locales/*.json` (×6) | Add `search.*` and `export.*` i18n keys |
| `frontend/src/App.vue` | Register global `Cmd+K` / `Ctrl+K` keyboard shortcut |

---

## Testing Strategy

### Search Tests (`test_search.py`)

- Search with no results returns 200 + empty list
- Keyword matches in messages are returned with correct snippet
- Keyword at start of content (pos=0): snippet is not prefixed with garbage
- Keyword at end of content: snippet is not suffixed with garbage
- Keyword matches in documents (by filename) are returned; soft-deleted documents are **excluded**
- Keyword matches in memories are returned
- `types=messages` filter excludes documents and memories
- `types=foobar` returns 422
- `date_from` / `date_to` filter works correctly
- User A cannot see User B's results (isolation)
- `q` shorter than 3 chars returns 422
- `q` longer than 200 chars returns 422
- Rate limit enforced (mock limiter, verify user-ID key not IP)
- Workspace member can find messages from workspace conversations

### Conversation Export Tests (`test_conversations.py` — extend existing)

- Single conversation Markdown export: correct format (title, metadata header, messages), correct `Content-Disposition: attachment`
- Single conversation Markdown with > 1000 messages: returns most recent 1000, includes truncation note
- Single conversation JSON export: valid JSON, `truncated` field present, all messages present (up to 1000)
- Export of another user's conversation returns 404

### Account Export Tests (`test_export.py`)
- Account export `POST` returns 200 and enqueues ARQ task
- Account export atomic cooldown: concurrent requests cannot both succeed (mock Redis SET NX)
- Second account export request within 24h returns 429 with `retry_after`
- `export_account` ARQ task produces ZIP containing `conversations/`, `documents.json`, `memories.json`, `settings.json`
- ZIP `settings.json` does **not** contain `api_keys` values (replaced with `[REDACTED]`)
- ZIP uses temp file, not in-memory BytesIO (verify `tempfile.NamedTemporaryFile` called)
- Status endpoint reflects `pending` → `done` transition
- Status endpoint returns 200 with empty status (no prior export) gracefully
- `cleanup_expired_exports` cron deletes the correct MinIO object key and removes it from the Redis sorted set
- `cleanup_expired_exports` with MinIO failure: key remains in sorted set, no exception propagated

---

## Out of Scope

- Semantic search (vector-based) — RAG tool already covers this use case
- Export of raw document files (MinIO objects) — metadata only to keep ZIP size manageable
- Import of previously exported data — future phase
- PDF rendering of exported conversations — Markdown is sufficient for Phase 21
- DB-backed export status table — Redis-based status with documented TTL loss is acceptable for Phase 21
