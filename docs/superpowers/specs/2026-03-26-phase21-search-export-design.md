# Phase 21: Search & Export Design Spec

> Generated: 2026-03-26
> Status: Draft
> Scope: Full-text search across conversations/documents/memories + single-conversation and full-account data export

---

## Background

JARVIS has completed Phases 1-20, delivering a full-featured AI assistant platform with RAG, multi-LLM support, multi-tenancy, workflow studio, voice, monitoring, and comprehensive security hardening. Phase 21 targets two user-experience gaps that become increasingly painful as users accumulate data:

1. **No way to find past conversations** — users must scroll through conversation history to locate specific content
2. **No way to export data** — users cannot back up, migrate, or share their conversation history and knowledge base

---

## Sub-system 1: Full-Text Search

### Goal

A unified search endpoint that queries `messages.content`, `documents.filename`, and `user_memories.content` using PostgreSQL ILIKE with `pg_trgm` GIN index acceleration. Results are returned in a single ranked list with contextual snippets.

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
| `q` | string (1–200 chars) | required | Search keyword |
| `types` | comma-separated: `messages,documents,memories` | all | Scope of search |
| `date_from` | ISO 8601 date | none | Filter results after this date |
| `date_to` | ISO 8601 date | none | Filter results before this date |
| `limit` | int (1–50) | 20 | Max results per type |

**Authentication**: Required (JWT / PAT). Users only see their own data.

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
- Pattern: `%{q}%` (parameterized to prevent SQL injection)
- Snippet extraction: locate first match position, slice `[max(0, pos-80):pos+80+len(q)]`
- Results merged and sorted by `created_at DESC`
- Rate limited: 30 requests/minute per user

**Workspace scope**: Messages from workspace conversations that the user is a member of are included. Documents from accessible workspaces are included.

#### Database Migration

New Alembic migration (`041_add_search_gin_indexes.py`):

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY ix_messages_content_trgm
    ON messages USING gin (content gin_trgm_ops);

CREATE INDEX CONCURRENTLY ix_memories_content_trgm
    ON user_memories USING gin (content gin_trgm_ops);

CREATE INDEX CONCURRENTLY ix_documents_filename_trgm
    ON documents USING gin (filename gin_trgm_ops);
```

`CREATE INDEX CONCURRENTLY` avoids table lock. Alembic migration wraps each in a separate transaction (required for CONCURRENTLY).

### Frontend

#### New Route and Page

- Route: `/search` added to `frontend/src/router/index.ts` (requires auth)
- Page: `SearchPage.vue` — search input, type filter chips, date range pickers, result list grouped by type
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
  "placeholder": "搜索对话、文档和记忆...",
  "types": {
    "messages": "对话消息",
    "documents": "文档",
    "memories": "记忆"
  },
  "noResults": "未找到相关内容",
  "resultCount": "共 {count} 条结果",
  "snippet": {
    "conversation": "来自对话：{title}",
    "document": "文档：{filename}",
    "memory": "记忆"
  }
}
```

### Error Handling

- `q` empty or > 200 chars → 422 with validation message
- Database unavailable → 503
- No results → 200 with empty `results` array (not 404)

---

## Sub-system 2: Data Export

### Goal

Two export modes:
1. **Single conversation export**: Synchronous download of one conversation as Markdown or JSON
2. **Full account export**: Asynchronous background job that packages all user data into a ZIP, stores it in MinIO, and notifies the user with a time-limited download link

### Architecture

**New file**: `backend/app/api/export.py`
**New ARQ task**: `export_account` in `backend/app/worker.py`
**Frontend changes**: `ChatPage.vue` (per-conversation export button), `SettingsPage.vue` (account export section)

### Backend API

#### Single Conversation Export

**`GET /api/conversations/{id}/export`**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | `markdown` \| `json` | `markdown` | Export format |

**Authorization**: User must own the conversation (or be a workspace member if workspace conversation).

**Response**: `StreamingResponse` with appropriate `Content-Disposition` header:
- Markdown: `Content-Type: text/markdown`, filename `{conversation-title}.md`
- JSON: `Content-Type: application/json`, filename `{conversation-title}.json`

**Markdown format**:

```markdown
# {conversation title}

> Exported: {ISO date} · Model: {model_name} · Messages: {count}

---

**User** · {timestamp}
{message content}

**Assistant** · {timestamp}
{message content}
```

**JSON format**:

```json
{
  "id": "uuid",
  "title": "string",
  "model_name": "string",
  "created_at": "ISO 8601",
  "exported_at": "ISO 8601",
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

**Rate limit**: 20 exports/minute per user.

#### Full Account Export

**`POST /api/export/account`**

Enqueues an ARQ background job. Returns immediately:

```json
{ "task_id": "uuid", "message": "Export started. You will be notified when ready." }
```

**Rate limit**: 1 request per 24 hours per user (enforced via Redis key `export_cooldown:{user_id}` with 86400s TTL).

**`GET /api/export/account/status`**

```json
{
  "status": "pending|running|done|failed",
  "created_at": "ISO 8601",
  "download_url": "https://... (present only when status=done)",
  "expires_at": "ISO 8601 (present only when status=done)"
}
```

Status is stored in Redis key `export_status:{user_id}` (TTL 25 hours).

#### ARQ Worker Task: `export_account`

Steps executed in the background:

1. **Conversations + messages**: Query all user's conversations with messages ordered by `created_at`; serialize to individual Markdown files under `conversations/`
2. **Documents metadata**: Query `documents` table (non-deleted); serialize to `documents.json` (no raw file content — files may be large; metadata only)
3. **Memories**: Query `user_memories`; serialize to `memories.json`
4. **Settings**: Query `user_settings`; serialize to `settings.json` with sensitive fields redacted (`api_keys` → `"[REDACTED]"`, `persona_override` retained)
5. **Package**: Build ZIP in memory (`zipfile.ZipFile` with `io.BytesIO`)
6. **Upload**: `asyncio.to_thread(minio_client.put_object, ...)` to MinIO, object key `exports/{user_id}/{task_id}.zip`
7. **Presign**: Generate 24-hour presigned download URL
8. **Notify**: Insert `Notification` row (type `account_export_ready`, body contains download URL)
9. **Update Redis**: Set `export_status:{user_id}` to `done` with URL and expiry

**Error handling**: On any step failure, set Redis status to `failed`, insert `Notification` of type `account_export_failed`, log exception.

**Cleanup**: After 25 hours, a new cron job `cleanup_expired_exports` deletes the MinIO object and clears the Redis key.

### Frontend

#### Per-Conversation Export

`ChatPage.vue` conversation header (three-dot menu):
- New menu item: "导出对话"
- Sub-menu or modal: choose Markdown or JSON
- Triggers `window.open(url)` or fetch + `URL.createObjectURL` for download

#### Account Export (`SettingsPage.vue`)

New section "数据与隐私":
- "导出全部数据" button
- On click: POST `/api/export/account` → show toast "导出任务已提交，完成后将通知您"
- If 24h cooldown active: show remaining time "距下次可导出还有 Xh Xm"
- Notification center already shows the completion notification with download link

#### i18n Keys

```json
"export": {
  "title": "数据导出",
  "singleConversation": "导出对话",
  "formatMarkdown": "Markdown 格式",
  "formatJson": "JSON 格式",
  "accountExport": "导出全部数据",
  "accountExportHint": "将打包您的所有对话、文档元数据和记忆，API 密钥不会包含在导出中",
  "submitted": "导出任务已提交，完成后将通知您",
  "cooldown": "距下次可导出还有 {time}",
  "downloadReady": "您的数据导出已就绪，请在 24 小时内下载",
  "failed": "导出失败，请稍后重试"
}
```

### Security Constraints

- API keys, password hashes, and Fernet-encrypted values are **never** exported
- MinIO presigned URLs use 24-hour expiry; the underlying object is deleted after 25 hours
- Export task verifies `user_id` matches the authenticated user before packaging
- Single conversation export validates conversation ownership before streaming

---

## File Map

### New Files

| File | Purpose |
|------|---------|
| `backend/app/api/search.py` | Search endpoint |
| `backend/app/api/export.py` | Export endpoints (single conversation + account) |
| `backend/alembic/versions/041_add_search_gin_indexes.py` | pg_trgm extension + GIN indexes |
| `frontend/src/pages/SearchPage.vue` | Search UI page |
| `backend/tests/api/test_search.py` | Search endpoint tests |
| `backend/tests/api/test_export.py` | Export endpoint tests |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/main.py` | Register `search_router` and `export_router` |
| `backend/app/worker.py` | Add `export_account` ARQ task + `cleanup_expired_exports` cron |
| `backend/app/api/conversations.py` | Add `GET /{id}/export` endpoint |
| `frontend/src/router/index.ts` | Add `/search` route |
| `frontend/src/pages/ChatPage.vue` | Add search shortcut + conversation export button |
| `frontend/src/pages/SettingsPage.vue` | Add account export section |
| `frontend/src/locales/*.json` (×6) | Add `search.*` and `export.*` i18n keys |

---

## Testing Strategy

### Search Tests (`test_search.py`)

- Search with no results returns 200 + empty list
- Keyword matches in messages are returned with correct snippet
- Keyword matches in documents (by filename) are returned
- Keyword matches in memories are returned
- `types` filter correctly excludes non-requested types
- Date range filters work correctly
- User A cannot see User B's results (isolation)
- `q` too long returns 422
- Empty `q` returns 422
- Rate limit enforced (mock limiter)

### Export Tests (`test_export.py`)

- Single conversation Markdown export: correct format, correct `Content-Disposition`
- Single conversation JSON export: valid JSON, all messages present
- Export of another user's conversation returns 403/404
- Account export enqueues ARQ task, returns task_id
- Second account export within 24h returns 429 with cooldown info
- ARQ task produces ZIP with expected files
- ZIP does not contain `api_keys` values
- Status endpoint reflects task progress

---

## Out of Scope

- Semantic search (vector-based) — RAG tool already covers this use case
- Export of raw document files (MinIO objects) — metadata only to keep ZIP size manageable
- Import of previously exported data — future phase
- PDF rendering of exported conversations — Markdown is sufficient for Phase 21
