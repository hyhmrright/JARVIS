# JARVIS Product Roadmap Design

> **Status**: Approved
> **Date**: 2026-03-13
> **Goal**: Transform JARVIS into a production-ready multi-tenant AI assistant platform.

---

## Context

JARVIS is an AI assistant platform with RAG knowledge base, multi-LLM support, streaming conversations, proactive monitoring (cron/webhook/semantic), voice, canvas rendering, and a monitoring stack. The platform currently has several broken features, UX gaps, and lacks multi-tenant support.

**Priorities** (user-confirmed): Fix broken > UX polish > Stability/Ops > New features

**Target**: Multi-tenant SaaS — organizations with workspaces, team-shared resources, fine-grained permissions.

---

## Architecture Principles

- Each phase delivers fully working, shippable software
- Phase 1 pre-designs the DB schema for multi-tenancy to avoid future migrations
- No backwards-incompatible API changes without versioning
- All new endpoints follow existing auth/RBAC patterns
- Tests written before or alongside implementation (TDD)

---

## Phase 1: Fix Broken + Multi-tenant DB Predesign

**Goal**: Every existing feature actually works. DB is multi-tenant ready.

### Task 1.1 — Voice Complete Fix

**Problem**: Voice WebSocket is a non-functional stub with no authentication.

**Solution**:
- WebSocket auth: validate JWT via `?token=` query param on handshake (consistent with Canvas SSE pattern)
- STT: receive binary audio frames → call OpenAI Whisper API (`whisper-1`) → get transcript
- LLM: read user's `user_settings` for provider/model instead of hardcoded Deepseek
- TTS language: derive from user's i18n locale setting (zh→`zh-CN-XiaoxiaoNeural`, en→`en-US-JennyNeural`, ja→`ja-JP-NanamiNeural`, etc.)
- Error handling: STT failure, LLM failure, disconnection all handled gracefully with error messages sent before close
- Frontend: update `VoiceOverlay.vue` and `useVoiceStream.ts` to handle new JSON message protocol (`transcription` / `ai_text` / `done` / `error` events) and display live connection/transcription state (entry button already exists in `ChatPage.vue`)

**Files**:
- Modify: `backend/app/api/voice.py`
- Modify: `frontend/src/components/VoiceOverlay.vue`
- Modify: `frontend/src/composables/useVoiceStream.ts`
- Test: `backend/tests/api/test_voice.py`

### Task 1.2 — RAG Integration in Background Agent Tasks

**Problem**: RAG context injection only exists in `api/chat.py`. Cron jobs and webhook-triggered agents have no access to the user's knowledge base.

**Solution**:
- Extract `inject_rag_context(user_id: str, task_text: str, db: AsyncSession) -> str` as a shared utility in `backend/app/rag/context.py`
- The existing `maybe_inject_rag_context` in `gateway/router.py` is replaced by this shared function; its existing tests in `tests/gateway/test_gateway_rag.py` must be updated to match the new signature
- `gateway/router.py` updated to call the new shared function
- `gateway/agent_runner.py::run_agent_for_user()` gets RAG injection for the first time via `inject_rag_context()`
- Voice WebSocket also calls it after STT produces a transcript
- Returns enriched task string with retrieved context prepended; returns original string unchanged if no relevant chunks found or Qdrant unavailable

**Files**:
- Create: `backend/app/rag/context.py`
- Modify: `backend/app/gateway/router.py`
- Modify: `backend/app/gateway/agent_runner.py`
- Modify: `backend/app/api/chat.py`
- Modify: `backend/tests/gateway/test_gateway_rag.py` (update for new signature)
- Test: `backend/tests/rag/test_context.py`

### Task 1.3 — Multi-tenant DB Predesign

**Problem**: Adding multi-tenancy later would require large schema migrations. Pre-reserve fields now.

**Solution**:

New tables (models defined, no business logic yet):

```sql
organizations (
  id UUID PK,
  name VARCHAR(255),
  slug VARCHAR(100) UNIQUE,  -- URL-safe identifier
  owner_id UUID FK users,
  created_at TIMESTAMPTZ
)

workspaces (
  id UUID PK,
  name VARCHAR(255),
  organization_id UUID FK organizations,
  created_at TIMESTAMPTZ
)
```

Add nullable columns to existing tables (no FK constraint, just indexed):

| Table | Column | Type |
|-------|--------|------|
| `users` | `organization_id` | `UUID NULL` |
| `conversations` | `workspace_id` | `UUID NULL` |
| `documents` | `workspace_id` | `UUID NULL` |
| `cron_jobs` | `workspace_id` | `UUID NULL` |
| `webhooks` | `workspace_id` | `UUID NULL` |

Migration: single Alembic revision `013_multi_tenant_predesign`.

**Files**:
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/013_multi_tenant_predesign.py`
- Test: `backend/tests/db/test_multi_tenant_models.py`

### Task 1.4 — Cron Small Fixes

**Problem**: Several small but impactful gaps in the cron/scheduler system.

**Solutions**:

1. **`next_run_at`**: After registering/updating a job in APScheduler, call `scheduler.get_job(job_id).next_run_time` and write to `cron_jobs.next_run_at`. Frontend can display "Next run: in 2 hours".

2. **`chunk_count`**: On document soft-deletion, after Qdrant vector delete, set `document.chunk_count = 0` in DB (ensures accurate count if the record is ever audited or undeleted in future).

3. **Cron lock TTL**: Add `CRON_LOCK_TTL_SECONDS` to settings (default: `max(300, job_timeout * 2)`). Workers read this setting.

4. **Trigger metadata validation**: New module `backend/app/scheduler/trigger_schemas.py` with per-type Pydantic models:
   - `CronTriggerMetadata` — no extra fields
   - `WebWatcherMetadata` — requires `url: HttpUrl`
   - `SemanticWatcherMetadata` — requires `url: HttpUrl`, `target: str`; optional `fire_on_init: bool`
   - `EmailWatcherMetadata` — requires `imap_host`, `email_address`; optional `imap_port`, `imap_folder`
   - `POST /api/cron` validates against the relevant schema on creation, returns 422 on violation
   - Also add `PUT /api/cron/{id}` update endpoint (currently missing); validates same schema

**Files**:
- Modify: `backend/app/scheduler/runner.py`
- Modify: `backend/app/api/cron.py`
- Modify: `backend/app/api/documents.py`
- Create: `backend/app/scheduler/trigger_schemas.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/scheduler/test_trigger_schemas.py`
- Test: `backend/tests/api/test_cron.py` (new PUT endpoint + next_run_at)

### Task 1.5 — JobExecution Data Retention

**Problem**: `job_executions` table grows unbounded with no cleanup mechanism.

**Solution**:
- Add `CRON_EXECUTION_RETENTION_DAYS` to settings (default: 90)
- New ARQ periodic function `cleanup_old_executions()`: runs daily at 03:00 UTC, deletes records where `fired_at < now() - retention_days` (column is named `fired_at` in the `JobExecution` model)
- Register as an ARQ `cron` task in `WorkerSettings`
- Log count of deleted rows

**Files**:
- Modify: `backend/app/worker.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_worker.py`

---

## Phase 2: UX Polish

**Goal**: Product is demo-ready. Interactions feel complete and professional.

### Task 2.1 — Chat Streaming Cancel

**Problem**: No way to interrupt a hung or slow LLM response.

**Solution**:
- Frontend: `AbortController` stored in chat store; "Stop generating" button appears during streaming; `abort()` on click
- Backend: SSE generator polls `await request.is_disconnected()` every N tokens; on disconnect, stops LangGraph execution and saves partial response to DB as an `assistant` message with `[已中断]` suffix
- Button disappears after stream ends or is cancelled

**Files**:
- Modify: `frontend/src/stores/chat.ts`
- Modify: `frontend/src/pages/ChatPage.vue`
- Modify: `backend/app/api/chat.py`

### Task 2.2 — Document Upload Progress + Unified Error Toasts

**Problem**: No upload progress feedback; error handling is inconsistent across pages.

**Solution**:
- Upload progress: Axios `onUploadProgress` callback updates a reactive `uploadProgress: number` in the store; progress bar shown in DocumentsPage
- Unified error format: Backend standardizes error responses as `{ code: str, message: str, detail: any }` across all endpoints
- Frontend: Global `useToast()` composable (or lightweight toast library); all API errors flow through it
- Replace per-page `alert()` and inline error divs with toast notifications

**Files**:
- Modify: `frontend/src/pages/DocumentsPage.vue`
- Create: `frontend/src/composables/useToast.ts`
- Modify: `frontend/src/api/` (axios response interceptor)
- Modify: `backend/app/core/` (exception handlers)

### Task 2.3 — i18n Completeness

**Problem**: Several pages have hardcoded strings; 4 non-English languages have missing keys.

**Solution**:
- Audit all `.vue` files for hardcoded user-visible strings; move to i18n keys
- ProactivePage: "Never run", status badges, emoji labels → i18n
- Voice page translations
- Canvas-related strings
- Use AI-assisted translation to fill missing keys in `ja.json`, `ko.json`, `fr.json`, `de.json`
- Add CI check: `bun run i18n:check` that fails if zh.json has keys missing from other locale files

**Files**:
- Modify: `frontend/src/pages/*.vue`
- Modify: `frontend/src/locales/*.json` (all 6)
- Create: `frontend/scripts/check-i18n.ts`

### Task 2.4 — Trigger Metadata Schema Validation (Frontend)

**Problem**: Frontend form allows creating invalid cron jobs (e.g., SemanticWatcher without URL).

**Solution**:
- Form validation in ProactivePage: required fields per trigger type enforced before submit
- Display field-level error messages (not just API error toasts)
- Consistent with backend Task 1.4 validation (422 errors also displayed gracefully)

**Files**:
- Modify: `frontend/src/pages/ProactivePage.vue`

---

## Phase 3: Stability / Ops

**Goal**: Production-safe. Observable. Resilient to failure.

### Task 3.1 — AgentSession Metadata Population

**Problem**: `AgentSession.context_summary` and `metadata_json` are never written, losing observability.

**Solution**:
- `AgentSession` is currently only created and managed in `api/chat.py`; background runs (`agent_runner.py`) do not create sessions at all
- Task 3.1 does two things:
  1. In `chat.py`: after context compression fires, write the compressed summary to `AgentSession.context_summary`; after each LLM response, append model/tool/token data to `AgentSession.metadata_json`
  2. In `agent_runner.py`: introduce `AgentSession` tracking for background runs (cron/webhook) — create a session record at run start, write `metadata_json` at completion
- Data written: `{ "model": "deepseek-chat", "tools_used": ["search"], "input_tokens": 1200, "output_tokens": 340, "trigger_type": "cron" }`

**Files**:
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/gateway/agent_runner.py` (new AgentSession creation for background runs)

### Task 3.2 — Webhook Async Delivery + Retry

**Problem**: Webhook triggers are synchronous with no retry mechanism. A slow target URL blocks the request.

**Solution**:
- New DB table: `webhook_deliveries (id, webhook_id, triggered_at, status, response_code, response_body, attempt, next_retry_at)`
- Webhook trigger moves to ARQ async task `deliver_webhook(webhook_id, run_group_id)`
- Retry policy: 3 attempts, exponential backoff (1s, 10s, 60s)
- New endpoint: `GET /api/webhooks/{id}/deliveries` — returns last 20 delivery records
- Frontend: delivery history tab in webhook detail view

**Files**:
- Modify: `backend/app/api/webhooks.py`
- Modify: `backend/app/worker.py`
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/014_webhook_deliveries.py`

### Task 3.3 — Prometheus Metrics + Grafana Alerts

**Problem**: No custom application metrics; no alerting on failure conditions.

**Solution**:
- Add `prometheus-client` to backend; expose `GET /metrics` (IP-allowlisted, not behind JWT)
- Custom counters/histograms:
  - `jarvis_cron_executions_total{status=success|failure|skipped}`
  - `jarvis_rag_retrieval_duration_seconds`
  - `jarvis_llm_requests_total{provider, model, status}`
  - `jarvis_arq_queue_depth`
- Grafana alert rules:
  - ARQ queue depth > 50 for 5 minutes → warning
  - Cron failure rate > 20% over 1 hour → critical
  - API P99 latency > 5s → warning
- Alert notification channel: configurable webhook (Slack/email) via `ALERT_WEBHOOK_URL` env var

**Files**:
- Modify: `backend/app/main.py`
- Create: `backend/app/core/metrics.py`
- Create: `monitoring/grafana/provisioning/alerting/` (directory does not currently exist)
- Modify: `monitoring/prometheus.yml`

---

## Phase 4: Multi-tenant Full Implementation

**Goal**: Complete Organization/Workspace model with team sharing and fine-grained permissions.

### Task 4.1 — Organization + Workspace CRUD API

**Activates Phase 1 pre-built schema.**

- `POST /api/organizations` — create org (caller becomes owner)
- `GET /api/organizations/me` — get current user's org
- `PUT /api/organizations/{id}` — update name/slug (owner only)
- `POST /api/workspaces` — create workspace within org
- `GET /api/workspaces` — list user's accessible workspaces
- `PUT /api/workspaces/{id}` — update (admin+)
- `DELETE /api/workspaces/{id}` — soft delete (owner only)
- User registration: optionally `POST /api/organizations` then auto-create default workspace

**Files**:
- Create: `backend/app/api/organizations.py`
- Create: `backend/app/api/workspaces.py`
- Modify: `backend/app/db/models.py` (activate org/workspace relationships)
- Create: `backend/alembic/versions/015_activate_multi_tenant.py`

### Task 4.2 — Membership + Invitation System

**New tables** (added in migration `016_workspace_members_invitations`, separate from Task 4.1's migration `015`):
```
workspace_members (workspace_id, user_id, role: owner|admin|member, joined_at)
invitations (id, workspace_id, inviter_id, email, token UUID, role, expires_at, accepted_at)
```

- `POST /api/workspaces/{id}/members/invite` — send invite (generates token, optionally emails)
- `GET /api/invitations/{token}` — preview invite details (public)
- `POST /api/invitations/{token}/accept` — accept invite (requires login)
- `PUT /api/workspaces/{id}/members/{user_id}` — change role (admin+)
- `DELETE /api/workspaces/{id}/members/{user_id}` — remove member (admin+)
- Invitation links expire after 7 days

**Files**:
- Create: `backend/app/api/invitations.py`
- Modify: `backend/app/api/workspaces.py`
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/016_workspace_members_invitations.py`

### Task 4.3 — Shared Resources (Documents, Cron Jobs)

**Activates `workspace_id` fields across resource tables.**

- **Documents**: upload form adds "Personal / Workspace: [name]" selector
  - Personal docs: `workspace_id = NULL`, visible only to owner
  - Workspace docs: `workspace_id = X`, visible to all workspace members
  - RAG retrieval: searches personal docs + all workspace docs user has access to
- **Cron Jobs**: creation form adds workspace selector
  - Workspace cron jobs editable by workspace admins, visible to all members
- **Conversations**: remain personal by default; future: shareable to workspace
- **Permissions**: workspace `member` can read shared docs/crons; `admin` can create/edit/delete

**Files**:
- Modify: `backend/app/api/documents.py`
- Modify: `backend/app/api/cron.py`
- Modify: `backend/app/rag/retriever.py`
- Modify: `backend/app/rag/context.py`
- Modify: `frontend/src/pages/DocumentsPage.vue`
- Modify: `frontend/src/pages/ProactivePage.vue`

### Task 4.4 — Workspace LLM Settings

**Problem**: Each user must configure their own API keys. Teams want shared keys.

**Note**: Depends on Task 4.1 (workspaces table must exist before this task).

**Solution**:
- New table: `workspace_settings (workspace_id UUID PK FK workspaces.id, settings_json JSONB, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)` — same Fernet-encrypted structure as `user_settings`
- LLM resolution priority: personal API key → workspace API key → system default (env var)
- `GET/PUT /api/workspaces/{id}/settings` — workspace admin only
- Frontend: Settings page adds "Workspace Settings" tab when user is workspace admin

**Files**:
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/api/settings.py` (or new `workspaces.py`)
- Modify: `backend/app/agent/llm.py` (resolution logic)
- Modify: `frontend/src/pages/SettingsPage.vue`
- Create: `backend/alembic/versions/017_workspace_settings.py`

### Task 4.5 — Frontend Multi-tenant UI

**Solution**:
- **Workspace switcher**: top navbar dropdown showing current workspace; click to switch
- **Members page**: new route `/workspace/members` — list members, invite form, role management
- **Invitation accept page**: `/invite/{token}` — shows workspace name, role, accept/decline buttons
- **Resource ownership selectors**: documents and cron jobs show personal/workspace toggle on creation
- **Settings**: workspace settings tab for admins

**Files**:
- Modify: `frontend/src/router/`
- Create: `frontend/src/pages/WorkspaceMembersPage.vue`
- Create: `frontend/src/pages/InviteAcceptPage.vue`
- Modify: `frontend/src/pages/SettingsPage.vue`
- Modify: `frontend/src/pages/DocumentsPage.vue`
- Modify: `frontend/src/pages/ProactivePage.vue`
- Create: `frontend/src/components/WorkspaceSwitcher.vue`
- Create: `frontend/src/stores/workspace.ts`

---

## Summary

| Phase | Tasks | Key Deliverable |
|-------|-------|-----------------|
| **Phase 1** | 5 | All features work; DB multi-tenant ready |
| **Phase 2** | 4 | Demo-ready UX; complete i18n |
| **Phase 3** | 3 | Production-stable; observable; resilient |
| **Phase 4** | 5 | Full multi-tenant SaaS |
| **Total** | **17** | Production-grade AI assistant platform |

---

## Testing Strategy

- Every task ships with tests (TDD where practical)
- API endpoint tests use existing `client` + `auth_headers` fixtures
- Unit tests for business logic (RAG context, trigger schemas, LLM resolution)
- No mocking the database in integration tests (learned from past incidents)
- CI must stay green after each task
