# Phase 16-20: JARVIS Comprehensive Upgrade Design Spec

> Generated: 2026-03-25
> Status: Draft
> Scope: 30+ issues across 5 phases covering bug fixes, security, features, and quality

## Background

A full-codebase audit identified 30+ issues across backend API, frontend UI, infrastructure/security, and AI agent/RAG systems. Issues range from Critical (broken functionality) to Medium (missing polish). This spec organizes all fixes into 5 phases using a vertical-slice strategy: each phase focuses on a subsystem and addresses bugs + security + features + tests within that subsystem.

## Phase 16: Critical Bug Sweep + Infrastructure Hardening

**Goal**: Eliminate all Critical-severity functional breakage and harden the database/Docker foundation layer. Smallest and fastest phase.

### 16.1 Frontend Folder Store Double-Prefix Fix

**Problem**: `stores/chat.ts` lines 144/153/163/172/186 use `"/api/folders"` as the path, but the Axios client already has `baseURL: "/api"`, resulting in requests to `/api/api/folders` (404). All drag-and-drop folder features are broken in production.

**Fix**: Change all five occurrences from `"/api/folders"` to `"/folders"`.

**Files**: `frontend/src/stores/chat.ts`

### 16.2 Agent Approval Node Dead End Fix

**Problem**: `agent/graph.py` registers `graph.add_node("approval", ask_approval)` but never adds an outbound edge from the approval node. The approval flow is entirely non-functional.

**Fix**: Add `graph.add_edge("approval", END)`. The approval node writes `pending_tool_call` to state and the graph ends. When the user sends `[CONSENT:ALLOW]` or `[CONSENT:DENY]`, `chat.py` creates a new graph invocation with the `approved` field set, which triggers the `review_output` node via the existing conditional edge from `tools`.

**Files**: `backend/app/agent/graph.py`

**Verification**: Confirm the frontend's consent handling in `chat.py` (lines 453-456) correctly populates the `approved` field and that `review_output` executes the approved tool call.

### 16.3 Webhook Secret Token Encryption

**Problem**: `db/models.py` line 474 stores `secret_token` as plaintext `String(255)`. Unlike API keys (SHA-256 hashed) or user API keys (Fernet-encrypted), webhook secrets are immediately exposed if the database is breached.

**Fix**:
- Change `secret_token` column to store Fernet-encrypted values using existing `core/security.py` `encrypt_value()`/`decrypt_value()`
- New Alembic migration: batch-encrypt all existing plaintext tokens
- `webhooks.py`: encrypt on create, decrypt on verification

**Files**: `backend/app/db/models.py`, `backend/app/api/webhooks.py`, new migration file

### 16.4 Missing Database Indexes

**Problem**: Several frequently-queried FK columns lack indexes, causing sequential scans on growing tables.

**Fix**: New Alembic migration adding:
- `ix_personas_user_id` on `personas.user_id`
- `ix_workflows_user_id` on `workflows.user_id`
- `ix_workflow_runs_user_id` on `workflow_runs.user_id`
- `ix_installed_plugins_installed_by` on `installed_plugins.installed_by`
- `ix_notifications_user_read_created` composite on `notifications(user_id, is_read, created_at DESC)`

Remove redundant single-column indexes on `audit_logs.user_id` and `audit_logs.action` (covered by existing composite index `ix_audit_logs_action_user_created`).

**Files**: New migration file, `backend/app/db/models.py` (add `index=True` annotations)

### 16.5 Docker Hardening

**Problem**: No resource limits on any container; worker has no healthcheck; backend healthcheck doesn't verify DB connectivity.

**Fix**:
- `docker-compose.yml`: Add `deploy.resources.limits` for backend (1 CPU, 1GB), worker (1 CPU, 512MB), frontend (0.5 CPU, 256MB)
- Worker service: Add healthcheck (`python -c "import redis; redis.from_url('...').ping()"` — verifies worker can reach Redis/ARQ)
- Backend healthcheck: Change from HTTP-only check to include a lightweight DB ping

**Files**: `docker-compose.yml`

### 16.6 Frontend Minor Fixes

- `AdminPage.vue` line 88: Bind plugin toggle `checked` to actual plugin enabled state instead of hardcoded `true`
- `stores/chat.ts` `deleteConversation()`: Re-throw error after `console.error` so ChatPage can display a toast

**Files**: `frontend/src/pages/AdminPage.vue`, `frontend/src/stores/chat.ts`

---

## Phase 17: Agent & RAG System Upgrade

**Goal**: Fix critical AI pipeline defects ensuring Agent execution is safe/controllable and RAG works effectively for Chinese content.

### 17.1 Agent Graph Execution Timeout

**Problem**: No upper bound on `graph.astream()` execution time. A misbehaving tool can stall indefinitely.

**Fix**: Wrap `graph.astream()` in `chat.py` with `asyncio.wait_for(timeout=300)` (5-minute default, configurable via `Settings.graph_timeout_seconds`). On timeout, emit `{"type": "error", "message": "execution_timeout"}` SSE event before closing. Apply same pattern to `subagent_tool.py` `graph.ainvoke()` with 120s timeout.

**Files**: `backend/app/api/chat.py`, `backend/app/tools/subagent_tool.py`, `backend/app/core/config.py`

### 17.2 Tool Timeout Completion

**Problem**: `search_tool.py` (Tavily API), `image_gen_tool.py` (OpenAI), and `shell_tool.py` (unbounded user-specified timeout) have no or insufficient timeouts.

**Fix**:
- `search_tool.py`: Wrap Tavily call with `asyncio.wait_for(timeout=15)`
- `image_gen_tool.py`: Add `timeout=60` to OpenAI call
- `shell_tool.py`: Cap `timeout_seconds` at `min(timeout_seconds, 120)`

**Files**: `backend/app/tools/search_tool.py`, `backend/app/tools/image_gen_tool.py`, `backend/app/tools/shell_tool.py`

### 17.3 Code Execution Sandbox Unification

**Problem**: `code_exec_tool.py` uses `subprocess.run` directly on the host (not Docker), and `RLIMIT_AS` is silently skipped on macOS. Inconsistent with `shell_tool.py` which uses Docker sandbox.

**Fix**: When `settings.sandbox_enabled=True`, execute Python code via Docker sandbox (same mechanism as shell_tool). When `sandbox_enabled=False`, refuse execution (consistent with shell_tool). Remove macOS RLIMIT skip logic.

**Files**: `backend/app/tools/code_exec_tool.py`

### 17.4 SSRF Protection Hardening

**Problem**: `browser_tool.py` and `web_fetch_tool.py` check IP literals against blocked networks but pass DNS names through unresolved, enabling DNS rebinding attacks.

**Fix**: Extract shared `resolve_and_check_ip(hostname: str) -> str` to `core/network.py`. Resolves hostname via `socket.getaddrinfo`, checks all resolved IPs against `_BLOCKED_NETWORKS`. Applied in browser_tool, web_fetch_tool, and documents.py `ingest-url`.

**Files**: New `backend/app/core/network.py`, `backend/app/tools/browser_tool.py`, `backend/app/tools/web_fetch_tool.py`, `backend/app/api/documents.py`

### 17.5 RAG CJK Chunking Fix

**Problem**: `rag/chunker.py` uses `str.split()` (whitespace tokenization). CJK text has no whitespace between characters, producing one massive chunk for entire documents.

**Fix**: Language-aware chunking strategy:
- Detect CJK content (>30% CJK characters)
- CJK: Character-count windows (~1000 chars, 100 overlap), preferring sentence boundaries (。！？\n)
- Non-CJK: Keep existing word-level chunking
- Both: Prefer splitting at Markdown heading boundaries (`# `)

**Files**: `backend/app/rag/chunker.py`

### 17.6 Memory Injection Overflow Protection

**Problem**: `_build_memory_message()` injects up to 100 memories x 2000 chars = 200K characters as a system message, easily exceeding any model's context window.

**Fix**:
- `_build_memory_message()`: Add 8000-character total cap; truncate by `updated_at DESC` (most recent first)
- `user_memory_tool.py`: Reduce `_RECALL_LIMIT` from 100 to 20, add total character cap

**Files**: `backend/app/api/chat.py`, `backend/app/tools/user_memory_tool.py`

### 17.7 LLM Fallback Fix

**Problem**: `create_graph()` accepts `fallback_providers` parameter but never passes it to `get_llm_with_fallback()`. Supervisor uses `get_llm()` directly with no fallback.

**Fix**:
- `create_graph()`: Pass `fallback_providers` through to `get_llm_with_fallback()`
- `supervisor.py`: Replace `get_llm()` with `get_llm_with_fallback()`

**Files**: `backend/app/agent/llm.py`, `backend/app/agent/supervisor.py`

### 17.8 Document Rename Qdrant Sync

**Problem**: `documents.py` rename endpoint updates `filename` in PostgreSQL but not the `doc_name` field in Qdrant point payloads. RAG citations show stale document names.

**Fix**: After DB rename, call `q_client.set_payload()` with filter `doc_id == doc.id` to update `doc_name` in all associated Qdrant points.

**Files**: `backend/app/api/documents.py`

### 17.9 File Upload MIME Validation + Orphan Cleanup

**Problem**: `documents.py` upload relies entirely on client-supplied file extension (`rsplit(".", 1)[-1]`). No magic-byte validation — a polyglot file (e.g., executable disguised as `.pdf`) passes the check. Additionally, if `index_document` or `db.commit()` fails after MinIO `put_object` succeeds, the MinIO object is orphaned with no cleanup.

**Fix**:
- Add `python-magic` dependency; after extension check, validate first 2048 bytes against expected MIME types (`application/pdf`, `application/vnd.openxmlformats-officedocument.*`, `text/plain`, `text/csv`, `text/markdown`)
- Wrap the upload+index+commit sequence in try/finally: on failure, call `minio_client.remove_object()` to clean up the orphaned object

**Note**: `python-magic` requires system `libmagic`. Add `apt-get install -y libmagic1` to `backend/Dockerfile`.

**Files**: `backend/app/api/documents.py`, `backend/pyproject.toml`, `backend/Dockerfile`

### 17.10 SSE Heartbeat + Error Events

**Problem**: No keepalive comments in SSE streams (proxies cut idle connections). Agent exceptions cause abrupt stream close with no error event to the client.

**Fix**:
- SSE generators: Emit `": ping\n\n"` every 15 seconds during idle periods
- Agent exception handler: Emit `{"type": "error"}` SSE event before re-raising
- `chat.py:983-984`: Change `except Exception: pass` to `logger.warning`

**Files**: `backend/app/api/chat.py`, `backend/app/api/canvas.py`

---

## Phase 18: Workflow Studio & Persona Enhancement

**Goal**: Make Workflow Studio a functional workflow engine and give Personas fine-grained control.

### 18.1 Workflow Backend Execution Endpoints

New endpoints in `workflows.py`:
- `POST /api/workflows/{workflow_id}/execute` — Accepts `inputs: dict`, compiles DSL to LangGraph, creates `WorkflowRun` record, returns SSE stream with per-node status events (`node_start`/`node_output`/`node_error`/`done`)
- `GET /api/workflows/{workflow_id}/runs` — Paginated run history (status/started_at/finished_at/error), supports `limit`/`offset`

**Files**: `backend/app/api/workflows.py`

### 18.2 Graph Compiler Enhancement

Current state: Only `llm` nodes are functional; `condition`/`tool`/`output`/`image_gen` compile to identity no-ops.

**Fix**:
- **`tool` node**: Compile to invoke the specified agent tool by `tool_name` from the registered tools registry
- **`condition` node**: Compile to `add_conditional_edges` based on `condition_expression` evaluated against previous node output, routing to `true_handle` or `false_handle` edges. **Safety constraint**: Expressions must use Jinja2 templates only (e.g., `{{ nodes.node_1.output | length > 0 }}`), evaluated via `jinja2.sandbox.SandboxedEnvironment`. No arbitrary code evaluation — this is a hard security requirement
- **`output` node**: Compile as terminal node that formats final output and writes to `WorkflowRun.result`
- **`image_gen` node**: Compile to invoke `image_gen_tool`

**Files**: `backend/app/agent/compiler.py`

### 18.3 Inter-Node Variable Passing

**Problem**: No data flow between nodes.

**Fix**:
- `GraphState` adds `node_outputs: dict[str, Any]`
- Each node writes output to `node_outputs[node_id]` after execution
- LLM node `prompt_template` supports `{{nodes.node_id.output}}` template variables
- Frontend property panel adds variable selector dropdown listing connected upstream node outputs

**Files**: `backend/app/agent/compiler.py`, `frontend/src/pages/WorkflowStudioPage.vue`

### 18.4 Workflow DSL Schema Validation

**Problem**: `WorkflowCreate.dsl: dict` accepts arbitrary JSON with no validation.

**Fix**: Pydantic schemas for DSL structure:
- `WorkflowDSL(nodes: list[NodeDef], edges: list[EdgeDef])`
- `NodeDef` as discriminated union by `type` field: `LLMNodeDef` / `ToolNodeDef` / `ConditionNodeDef` / `OutputNodeDef` / `ImageGenNodeDef`
- Validation: no orphan nodes, exactly one entry node, DAG cycle detection

**Files**: `backend/app/api/workflows.py` (new schema definitions)

### 18.5 Frontend Studio Adaptation

- `WorkflowStudioPage.vue`: Connect `onRun()` to real `POST /execute` SSE stream
- Run History tab: Connect to `GET /runs` endpoint
- Property panel: Add variable reference UI
- `condition` node: Add custom Vue component with expression editor
- Execution timeout: Show timeout warning after 30s of no SSE events + cancel button

**Files**: `frontend/src/pages/WorkflowStudioPage.vue`

### 18.6 Persona System Enhancement

Extend `PersonaCreate` schema and `Persona` model:
- `temperature: float | None` — Optional, overrides user global temperature
- `model_name: str | None` — Optional, specifies preferred model
- `enabled_tools: list[str] | None` — Optional, restricts available tool subset (`None` = all)
- `replace_system_prompt: bool = False` — `True` fully replaces JARVIS base persona; `False` appends (backward compatible)

`chat.py` persona application: Read temperature/model/tools from persona and override graph creation parameters.

**Files**: `backend/app/api/personas.py`, `backend/app/db/models.py`, `backend/app/api/chat.py`, `backend/app/agent/persona.py`, new migration

### 18.7 Mid-Conversation Persona Switching

**Problem**: Persona only applied when `message_count == 0`.

**Fix**:
- `conversations` table: Add `persona_id` FK (migration)
- `PATCH /conversations/{id}`: Support updating `persona_id`
- Next message after switch uses new persona's configuration

**Files**: `backend/app/api/conversations.py`, `backend/app/db/models.py`, `backend/app/api/chat.py`, new migration

### Implementation Order Note

Within Phase 18, implement 18.4 (DSL Schema Validation) before 18.2 (Graph Compiler Enhancement) — the compiler consumes the Pydantic node types defined by the schema.

### Design Constraints

- No loop/cycle workflows (DAG only)
- No per-persona RAG scope

---

## Phase 19: Platform Robustness

**Goal**: Complete rate limiting, communication protocols, auth mechanisms, and CRUD gaps for production-grade robustness.

### 19.1 Rate Limiting Extension

Currently only auth/chat/documents/plugins/tts/cron have `@limiter.limit`. Add:

| Endpoint Group | Rate Limit | Rationale |
|---|---|---|
| `conversations.py` (all) | 60/min general, `search` 10/min | ILIKE full-table scan |
| `folders.py` | 30/min | |
| `memory.py` (`clear_all`) | 3/min | Bulk DELETE |
| `admin.py` | 60/min | Authenticated but needs abuse prevention |
| `invitations.py` (`GET /{token}`) | 20/min | Public endpoint, anti-enumeration |
| `gateway.py` (`POST /pair`) | 10/min | Pairing code brute-force prevention |
| `notifications.py`, `settings.py`, `workspaces.py`, `organizations.py`, `usage.py`, `public.py` | 60/min | Standard |

**Files**: All listed API files

### 19.2 SSE/WebSocket Communication

**WebSocket `/api/chat/ws`**: Remove the stub endpoint entirely. SSE is the mature streaming solution; maintaining two channels adds complexity with no benefit. Frontend does not use it.

**Voice Conversation Persistence**:
- `voice.py`: After each STT->LLM->TTS turn, persist user transcript and AI reply as `Message` records
- Add `conversation_id` parameter: voice session binds to a conversation (new or existing)
- Frontend voice mode: Add conversation selector

**Files**: `backend/app/api/chat.py` (remove WS), `backend/app/api/voice.py`

### 19.3 JWT Refresh Token

- New `refresh_tokens` table: `token_hash`, `user_id`, `expires_at`, `revoked_at`
- `POST /api/auth/login`: Return `access_token` (30-min) + `refresh_token` (7-day)
- `POST /api/auth/refresh`: Accept refresh_token, return new access_token
- `POST /api/auth/logout`: Revoke refresh_token
- **Token format**: Refresh token is an opaque random string (`secrets.token_urlsafe(64)`), stored as SHA-256 hash in DB. Stored in `localStorage` on the client (consistent with existing access token approach).
- Frontend Axios interceptor: On 401, attempt refresh then retry; if refresh fails, redirect to login
- `auth.ts` `logout()`: Call `notificationStore.stopPolling()`

**Files**: `backend/app/api/auth.py`, `backend/app/db/models.py`, new migration, `frontend/src/api/client.ts`, `frontend/src/stores/auth.ts`, `frontend/src/stores/notification.ts`

### 19.4 CRUD Completion

New endpoints:
- `GET /api/conversations/{conv_id}` — Single conversation metadata
- `DELETE /api/conversations/{conv_id}/share` — Revoke share link
- `PUT /api/memories/{memory_id}` — Edit memory
- `PATCH /api/webhooks/{webhook_id}` — Edit webhook name/task_template
- `DELETE /api/notifications/{id}` + `DELETE /api/notifications` — Delete notifications
- `GET /api/cron/{job_id}` — Single cron job
- `DELETE /api/organizations/{org_id}` — Delete organization (cascade workspaces/members)

Normalize all DELETE endpoints to return `204 No Content` (fix inconsistency in workflows/admin/personas/cron).

**Files**: All listed API files

### 19.5 Pagination Completion

Unified pattern: `limit`/`offset` query params + response `{ items: [], total: int }`:
- `GET /conversations/{id}/messages` — Remove 500 hard cap, add pagination (default limit=50)
- `GET /memories` — Add pagination
- `GET /personas` — Add pagination
- `GET /workflows` — Add pagination
- `GET /webhooks/{id}/deliveries` — Remove 20 hard cap, add pagination
- `GET /workspaces/{ws_id}/members` — Add pagination

**Frontend note**: `chat.ts` must be updated to implement incremental "load more" for message history (replacing the current single-fetch pattern), since existing code assumes all messages arrive in one call.

**Files**: All listed API files, `frontend/src/stores/chat.ts`

### 19.6 Worker Robustness

- **Dead letter queue**: New `dead_letter_jobs` table (job_id, function, args, error, failed_at). ARQ final failures write here instead of being silently dropped. Add monitoring alert.
- **`webhook_deliveries` cleanup**: Add deletion of records older than 30 days to `cleanup_old_executions` task
- **Webhook retry optimization**: `_WEBHOOK_RETRY_DELAYS` configurable via env var, default `[1, 10, 60, 300]` (4 retries, exponential growth)

**Files**: `backend/app/worker.py`, `backend/app/db/models.py`, new migration

### 19.7 Input Validation Hardening

| Field | File | Fix |
|---|---|---|
| `folders.color` | `folders.py` | Add `pattern=r'^#[0-9a-fA-F]{6}$'` |
| `cron.schedule` | `cron.py` | Add `@validator` with `croniter` syntax check |
| `auth.RegisterRequest.display_name` | `auth.py` | Add `max_length=100` |
| `chat.content` | `chat.py` | Add `min_length=1` |
| `settings.model_name` | `settings.py` | Validate against `PROVIDER_MODELS` on save |
| `tts.voice` | `tts.py` | Validate against known voice list |

**Files**: All listed API files

### 19.8 Workspace Permission Fix

- `workspaces.py` `update_workspace`: Add role check (owner/admin only)
- `documents.py` `PATCH`/`DELETE`: Add workspace admin permission (not limited to uploader)

**Files**: `backend/app/api/workspaces.py`, `backend/app/api/documents.py`

### Design Constraints

- Remove WebSocket chat stub (do not implement WebSocket chat)
- No CSRF token (JWT Bearer is sufficient)

---

## Phase 20: Quality & Observability

**Goal**: Complete test coverage, internationalization, accessibility, and monitoring alerts.

### 20.1 Test Coverage (7 Untested Modules)

**Note on test ownership**: Each phase writes tests for its own new code (e.g., Phase 18 writes tests for new workflow execute/runs endpoints). Phase 20.1 covers only **pre-existing untested modules** — testing code that existed before Phase 16 but had no tests. For modules modified by earlier phases, tests here cover the original functionality, not the new additions.

Priority order:
1. `test_documents.py` — Upload MIME validation, size limits, workspace permissions, soft delete + Qdrant cleanup, ingest-url SSRF
2. `test_settings.py` — API key Fernet round-trip, enabled_tools filtering, temperature range, model_name validation
3. `test_workflows.py` — CRUD operations only (execute/runs tests written in Phase 18)
4. `test_folders.py` — CRUD, display_order, color validation, cascade SET NULL
5. `test_chat_files.py` — MIME rejection, 10MB limit, PDF/DOCX parse failure, content truncation
6. `test_notifications.py` — List/mark-read/mark-all-read/delete, composite index performance
7. `test_logs.py` — No-auth access, rate limit, stack max_length

Also extend `test_admin.py`: Role escalation prevention, delete user.

**Files**: New test files in `backend/tests/api/`

### 20.2 i18n Full Coverage

**Hardcoded string extraction** (~40+ instances):
- `ChatPage.vue`: Notifications panel, Bookmarks, Pin/Unpin, Export menu, Empty folder, Recent, Add tag, Move to folder, Share Conversation, Welcome screen, Role labels, Edit/HITL UI, Regenerate, Token count, Model picker, Load more
- `WorkflowStudioPage.vue`: Run/Running, Execution Inputs, Execute Workflow, completion toast
- `ProactivePage.vue`: Target label

Extract all to `en.json`, then complete `zh.json`/`ja.json`/`ko.json`/`fr.json`/`de.json`.

**Missing locale keys** (12): `workflowStudio.*` (9 keys), `chat.extracting`, `chat.fileExtractionFailed`, `workflowStudio.nodeImage_gen`, `workflowStudio.nodeImage_genDesc`.

**Files**: All listed Vue files, all locale JSON files

### 20.3 Accessibility Improvements

- **Icon-only buttons**: Add `aria-label` to all text-less `<button>` elements (~30+ instances)
- **Modal focus traps**: Extract shared `useFocusTrap` composable; apply to AdminPage, ProactivePage, PersonasPage modals; add `@keydown.escape` close handler
- **`aria-live="polite"` regions**: Add to streaming message area and toast notification container
- **Skip-to-main-content link**: Add hidden link in `App.vue`
- **Replace `native confirm()`**: Replace 9 call sites with custom accessible confirmation dialog component

**Files**: Multiple Vue component files, new `useFocusTrap.ts` composable, new `ConfirmDialog.vue` component

### 20.4 Monitoring Alert Completion

New alert rules in `jarvis-alerts.yaml`:
- Backend down: `up{job="backend"} == 0` for 1 minute
- HTTP 5xx spike: 5xx rate > 5% for 5 minutes
- Worker stopped: `up{job="worker"} == 0` for 2 minutes (requires adding metrics endpoint to worker)
- DB connection pool high: `pg_stat_activity` active > 80% pool size
- Redis memory high: `redis_memory_used_bytes` > 80% maxmemory

Prometheus config:
- Add Qdrant scrape job (`:6333/metrics`)
- Add MinIO scrape job (`:9000/minio/v2/metrics/cluster`)

**Files**: `monitoring/grafana/provisioning/alerting/jarvis-alerts.yaml`, `monitoring/prometheus.yml`

### 20.5 Frontend Router Fixes

- New `NotFoundPage.vue`: Wildcard route shows 404 page instead of silent redirect to `/`
- Auth guard: Store `to.fullPath` in query param; redirect back after login
- Logged-in users visiting `/login`: Redirect to `/`
- `auth.ts` `logout()`: Call `notificationStore.stopPolling()` (same change as 19.3; implement in 19.3, verify here)

**Files**: `frontend/src/pages/NotFoundPage.vue`, `frontend/src/router/index.ts`, `frontend/src/stores/auth.ts`

### 20.6 Miscellaneous Cleanup

- `chat.py:983-984`: `except Exception: pass` -> `logger.warning`
- `documents.py`: Qdrant delete failure returns `207 Multi-Status` instead of silent 204
- `voice.py`: WebSocket auth timeout catches only `asyncio.TimeoutError`; explicit `await websocket.close()` after outer exception

**Files**: `backend/app/api/chat.py`, `backend/app/api/documents.py`, `backend/app/api/voice.py`

### Design Constraints

- No dark/light mode toggle (dark-only is a design decision)
- No global keyboard shortcuts / command palette (future phase)

---

## Phase Dependency Summary

```
Phase 16 (Critical Bugs + Infra)
    |
    v
Phase 17 (Agent & RAG)
    |
    v
Phase 18 (Workflow Studio & Persona)  -- depends on 17 for tool timeouts, graph timeout
    |
    v
Phase 19 (Platform Robustness)  -- depends on 18 for workflow test targets
    |
    v
Phase 20 (Quality & Observability)  -- depends on 16-19 for test targets
```

Phases are sequential. Each phase should be fully completed (including its own tests for new code) before starting the next.

## Issue Inventory

| # | Severity | Phase | Description |
|---|----------|-------|-------------|
| 1 | Critical | 16 | Frontend folder store double `/api/` prefix — all folder features broken |
| 2 | Critical | 16 | Agent approval node has no outbound edge — approval flow broken |
| 3 | Critical | 16 | Webhook `secret_token` stored as plaintext |
| 4 | Critical | 18 | Workflow Studio execute/runs endpoints don't exist; condition/tool/output nodes are no-ops |
| 5 | High | 17 | RAG chunking broken for CJK text |
| 6 | High | 17 | No agent graph execution timeout |
| 7 | High | 17 | `code_exec` runs on host subprocess, not Docker; macOS skips memory limits |
| 8 | High | 19 | Many endpoints have no rate limiting |
| 9 | High | 20 | 7 API modules have no tests |
| 10 | High | 16 | Missing database indexes on 5 columns |
| 11 | High | 16 | Docker: no resource limits, worker has no healthcheck |
| 12 | High | 17 | SSE has no heartbeat/reconnection hints |
| 13 | High | 19 | WebSocket `/api/chat/ws` is a non-functional stub |
| 14 | High | 19 | Voice conversations not persisted to DB |
| 15 | High | 20 | 40+ hardcoded English strings + 12 missing i18n keys |
| 16 | High | 20 | Accessibility nearly absent (no ARIA, no focus traps) |
| 17 | High | 19 | ARQ has no dead-letter queue |
| 18 | Medium | 17 | Memory injection can overflow context window (100x2000=200K chars) |
| 19 | Medium | 18 | Persona system: no temperature/model/tool control |
| 20 | Medium | 19 | Messages pagination hard-capped at 500; multiple endpoints lack pagination |
| 21 | Medium | 19 | Incomplete CRUD (missing GET single, UPDATE, revoke share, delete org) |
| 22 | Medium | 17 | `fallback_providers` parameter silently ignored; supervisor has no fallback |
| 23 | Medium | 17 | File upload extension-only validation; MinIO upload failure orphans objects |
| 24 | Medium | 17 | DNS rebinding SSRF in browser_tool/web_fetch_tool |
| 25 | Medium | 20 | Missing monitoring alerts (backend down, 5xx, worker stopped, etc.) |
| 26 | Medium | 19 | JWT 7-day expiry with no refresh token |
| 27 | Medium | 20 | Router: no 404 page, login doesn't preserve original URL |
| 28 | Medium | 16 | AdminPage plugin toggle `checked` hardcoded `true` |
| 29 | Medium | 19 | `webhook_deliveries` table grows unboundedly |
| 30 | Medium | 17 | Document rename doesn't update Qdrant `doc_name` payload |
