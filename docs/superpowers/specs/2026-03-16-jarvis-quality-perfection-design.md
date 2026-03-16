# JARVIS Quality Perfection Plan — Design Spec

**Date**: 2026-03-16
**Author**: Claude Code (brainstorming session)
**Status**: Approved by user

---

## Overview

A systematic plan to bring the JARVIS project to production-quality with zero known defects. Based on a comprehensive audit of the codebase, 35 issues were identified across security, stability, performance, and code quality dimensions; after consolidation (PR-35 merged into PR-31) and re-severity-classification, this yields **34 independent PRs**.

**Goal**: Fix all 35 issues (34 PRs after consolidation) as independent, reviewable PRs — each with a failing test that proves the bug, a fix, and a passing test that proves the fix.

**Approach**: Severity × Module dual-dimension ordering (Critical → High → Medium → Low), one PR per issue, each merged independently to `dev`.

---

## Constraints & Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scope | All 35 issues | Full quality, no shortcuts |
| Delivery | One PR per fix | Minimum releasable unit, lowest risk |
| Testing | Fix + accompanying test per PR | Proves fix works, prevents regression |
| Ordering | Critical → High → Medium → Low | Highest-impact problems first |
| Branch naming | `fix/<severity>-<module>-<desc>` | Clear, queryable git history |

---

## PR Execution Template

Every PR follows this exact sequence:

```
1. git checkout -b fix/<severity>-<module>-<desc> dev
2. Write failing test (proves bug exists)
3. Implement fix
4. Confirm test passes
5. Static checks:
   Backend:  cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
   Frontend: cd frontend && bun run lint:fix && bun run type-check
6. /simplify → commit → superpowers:code-reviewer → push → PR
```

---

## Phase 1 — Critical (4 PRs)

### PR-01: AsyncSessionLocal Cross-Event-Loop Contamination

**Branch**: `fix/critical-db-asyncsession-loop-contamination`
**File(s)**: `backend/tests/conftest.py`, `backend/app/api/deps.py`, `backend/app/worker.py`
**Problem**: Module-level `AsyncSessionLocal` binds connections to the current event loop. Each async test has its own loop, so subsequent tests fail with `"Future attached to a different loop"`.
**Fix**:
- Audit all code paths using module-level `AsyncSessionLocal` outside of request-scoped sessions (e.g., `log_action`, `_resolve_pat`, webhook delivery in `worker.py`)
- Add `autouse` mock fixtures in `conftest.py` for each path
- Follow existing pattern: `_suppress_auth_audit_logging`, `_suppress_pat_last_used_update`

**Test**: Full `pytest tests/` runs without `"Future attached to a different loop"` errors across all test files.

---

### PR-02: Missing Workspace Member Permission Checks

**Branch**: `fix/critical-security-workspace-permissions`
**File(s)**: `backend/app/api/workspaces.py`, `backend/app/api/documents.py`, `backend/app/api/cron.py`, `backend/app/api/deps.py`
**Problem**: Endpoints accepting `workspace_id` do not verify the requesting user is a member of that workspace. A user can access or modify another user's workspace data by guessing the workspace UUID.
**Fix**:
- Add `get_workspace_member(workspace_id: UUID, current_user: User = Depends(get_current_user))` dependency in `deps.py`
- Inject this dependency in all endpoints that accept `workspace_id`
- Return HTTP 403 if user is not a workspace member

**Test**: Non-member user calling `GET /api/documents?workspace_id=<other_workspace>` returns 403.

---

### PR-03: Qdrant Collection Creation Race Condition

**Branch**: `fix/critical-infra-qdrant-race-condition`
**File(s)**: `backend/app/infra/qdrant.py`
**Problem**: Between `collection_exists()` check and `create_collection()` call, a concurrent request can enter the same code path and both attempt to create the same collection. Qdrant rejects the second creation.
**Fix**:
- Wrap `create_collection()` in `try/except`
- Catch Qdrant "collection already exists" exception and continue silently
- Remove reliance on `_created_collections` set as sole guard

**Test**: 10 concurrent coroutines trigger `ensure_collection()` for the same user_id simultaneously — no exception raised, collection exists exactly once.

---

### PR-04: LLM Fallback Chain Exception Swallowing

**Branch**: `fix/critical-agent-llm-fallback-error-chain`

**File(s)**: `backend/app/agent/llm.py`
**Problem**: When all LLM providers fail, the last exception is logged but the caller receives a vague error without knowing which providers were tried and why each failed.
**Fix**:
- Collect `(provider_name, exception)` tuples in the fallback loop
- Define `LLMInitError(Exception)` with a `failures: list[tuple[str, Exception]]` field
- Raise `LLMInitError` with full failure chain when all fallbacks exhausted
- Log structured error with all provider failures

**Test**: Mock all providers to raise exceptions → caught `LLMInitError` contains failure details for each provider tried.

---

## Phase 2 — High (8 PRs)

### PR-05: RAG Overfetch with Non-Functional Mock Reranker

**Branch**: `fix/high-rag-overfetch-mock-reranker`
**File(s)**: `backend/app/rag/retriever.py`
**Problem**: Retriever fetches `top_k * 2` results then applies a mock reranker (keyword overlap boost) that provides no real quality improvement, wasting Qdrant I/O.
**Fix**:
- Change `limit` from `top_k * 2` to `top_k`
- Remove mock reranker logic
- Leave a documented `TODO: implement cross-encoder reranking` comment with interface placeholder
- Use chunk ID (not content string) for deduplication

**Test**: `retrieve(query, top_k=5)` returns exactly 5 results with no duplicates.

---

### PR-06: N+1 Queries in Admin Endpoints

**Branch**: `fix/high-db-admin-n-plus-one-queries`
**File(s)**: `backend/app/api/admin.py`
**Problem**: Listing users in the admin panel triggers one SQL query per user to fetch related data (organization, workspaces). With 100 users, this produces 100+ queries, causing the admin list endpoint latency to scale linearly with dataset size.
**Fix**: Add `selectinload(User.organization)` and `selectinload(User.workspaces)` to the user list query. Enforce `max limit=1000`, default `limit=50`, and `offset >= 0` validation.
**Test**: Listing 10 users generates ≤ 3 SQL queries total (verified with a SQLAlchemy `before_cursor_execute` event listener in the test).

---

### PR-07: Broad Exception Swallowing Without Logging

**Branch**: `fix/high-core-broad-exception-swallowing`
**File(s)**: `backend/app/channels/*.py`, `backend/app/rag/retriever.py`, `backend/app/core/limiter.py`
**Fix**: Replace all `except Exception: pass` / bare except with `logger.error(..., exc_info=True)`. Add Prometheus counter increment on each catch site.
**Test**: Trigger an exception in each patched path → verify log entry contains `exc_info`.

---

### PR-08: Public Share Token Predictability

**Branch**: `fix/high-security-public-share-token`
**File(s)**: `backend/app/api/public.py`, `backend/app/db/models.py` (shared_token field)
**Fix**:
- Replace UUID token with `secrets.token_urlsafe(32)` (256-bit entropy)
- Add rate limiting to `GET /api/public/conversations/{token}/messages`
- Log access to shared conversations in audit log

**Test**: Attack scenario — brute-force 1000 random tokens, verify all return 404 (token space too large to guess).

---

### PR-09: Shell Execution Sandbox Bypass

**Branch**: `fix/high-security-shell-sandbox-bypass`
**File(s)**: `backend/app/tools/shell_tool.py`, `backend/app/core/config.py`
**Fix**:
- Change default `SANDBOX_ENABLED=True` in config
- Replace substring blocklist with a strict allowlist of permitted commands
- Add test for known bypass patterns (`rm -rf /`, encoded variants)

**Test**: Known bypass strings (`"R\nM -RF /"`, `"dd if=/dev/zero"`) are blocked.

---

### PR-10: File Tool Symlink Path Traversal

**Branch**: `fix/high-security-file-tool-symlink`
**File(s)**: `backend/app/tools/file_tool.py`
**Fix**:
- Resolve the requested path fully with `os.path.realpath()` (which follows symlinks to their final target)
- Verify the resolved path starts with `os.path.realpath(WORKSPACE_ROOT)` — if not, reject with 403
- This ensures symlinks pointing outside the workspace (e.g., `/tmp/jarvis/{user_id}/link → /etc/passwd`) are caught after resolution

**Test**: Create a symlink inside workspace pointing to `/etc/passwd` → read attempt returns 403/error.

---

### PR-11: Message Branch Active Leaf Not Persisted

**Branch**: `fix/high-db-message-branch-persistence`
**File(s)**: `backend/app/db/models.py`, `backend/alembic/versions/`, `backend/app/api/conversations.py`, `frontend/src/stores/chat.ts`, `frontend/src/api/client.ts`
**Fix**:
- Add `active_leaf_message_id: UUID | None` column to `Conversation` model with `ForeignKey("messages.id", ondelete="SET NULL")`
- New alembic migration
- Add `ConversationUpdate(active_leaf_message_id: UUID | None)` Pydantic request schema
- Add `PATCH /api/conversations/{id}` endpoint accepting `ConversationUpdate` body; update the column and return updated conversation
- Update `GET /api/conversations/{id}` response schema to include `active_leaf_message_id`
- Add `patchConversation(id, body)` to `frontend/src/api/client.ts`
- In `frontend/src/stores/chat.ts`: after fetching a conversation, call `setActiveBranch(conversation.active_leaf_message_id)` if non-null; fallback to root message (first message with no parent) if null or if the referenced message is not found in the local message list

**Test**: Set active branch → call `PATCH` → reload page → verify frontend shows the same branch, not root.

---

### PR-12: Rate Limit Bypass via X-Real-IP Spoofing

**Branch**: `fix/high-security-rate-limit-ip-spoof`
**File(s)**: `backend/app/core/limiter.py`
**Fix**:
- For authenticated requests, always key rate limit by `user_id`, never fall back to IP
- For unauthenticated requests, validate `X-Real-IP` against a configurable trusted proxy CIDR
- Add `TRUSTED_PROXY_IPS` config variable

**Test**: Authenticated user with spoofed `X-Real-IP` header is still rate-limited by user_id.

---

## Phase 3 — Medium (11 PRs)

### PR-13: Exception Handling Without Recovery Logic
**Branch**: `fix/medium-core-exception-no-recovery`
**Fix**:
- Add a `@retry(max_attempts=3, base_delay=1.0, exceptions=(OSError, httpx.TransientError))` decorator (using `tenacity` library, already in pyproject.toml or add it) to channel adapter `send()` methods and RAG `retrieve()` calls
- Retry parameters: max 3 attempts, exponential backoff `base_delay * 2 ** attempt`, jitter ±0.1s, only on transient I/O exceptions (not `ValueError`, `AuthError`, etc.)
- Circuit breaker: after 5 consecutive failures on a channel, mark it as `OPEN` for 60 seconds (configurable via `CIRCUIT_BREAKER_THRESHOLD=5` and `CIRCUIT_BREAKER_TIMEOUT_SECONDS=60` in config)
- Log each retry attempt at `WARNING` level with attempt count and exception type

### PR-14: Organization Cascade Delete Missing
**Branch**: `fix/medium-db-org-cascade-delete`
**Fix**: Add `ondelete="CASCADE"` or explicit cleanup of workspaces/memberships when org deleted. New alembic migration.

### PR-15: WorkspaceSettings JSONB Schema Validation
**Branch**: `fix/medium-db-workspace-settings-jsonb`
**Fix**: Create `WorkspaceSettingsSchema` Pydantic model. Validate before saving to DB.

### PR-16: Admin Endpoint Missing Pagination Defaults
**Branch**: `fix/medium-api-admin-pagination-defaults`
**Fix**: Enforce `limit <= 1000`, default `limit=50`, `offset >= 0` on all admin list endpoints.

### PR-17: Document Upload Without Size Limit
**Branch**: `fix/medium-api-document-upload-size-limit`
**Fix**: Add `MAX_DOCUMENT_SIZE_BYTES = 100_000_000` to config. Validate before MinIO write. Return 413 on violation.

### PR-18: MCP Tools Create New Process Per Invocation
**Branch**: `fix/medium-tools-mcp-connection-reuse`
**Fix**: Implement a connection pool dict `{agent_session_id: MCPConnection}`. Reuse the connection for all tool calls with the same `agent_session_id`. Lifecycle:
- Connection created on first tool call for a given session
- Connection closed and removed from pool when the agent runner's `run()` method returns (normal completion) or raises (crash/exception) — use `try/finally` to guarantee cleanup
- Session timeout: add `MCP_SESSION_TIMEOUT_SECONDS=300` to config; a background task evicts idle connections older than this value
- Crash safety: if `run()` raises, the `finally` block must close the connection even if `agent_session_id` cleanup fails

**Test**: Two consecutive tool calls in the same agent session reuse the same process PID. A third call after session ends creates a new process.

### PR-19: CronJob Missing Unique Name Constraint
**Branch**: `fix/medium-db-cronjob-unique-name`
**Fix**: Add `UniqueConstraint("user_id", "name")` to CronJob model. New alembic migration.

### PR-20: WebhookDelivery Response Body Unbounded
**Branch**: `fix/medium-db-webhook-delivery-truncate`
**Fix**: Truncate `response_body` to 10KB before saving. Add `MAX_WEBHOOK_RESPONSE_BYTES = 10_240` to config.

### PR-21: Cron Schedule Syntax Not Validated at Creation
**Branch**: `fix/medium-scheduler-cron-syntax-validate`
**Fix**: Call `parse_trigger()` in `POST /api/cron` before saving. Return 400 with descriptive error on invalid syntax.

### PR-22: Frontend Doesn't Handle 429 Rate Limit Errors
**Branch**: `fix/medium-frontend-429-rate-limit-ux`
**Fix**: In Axios response interceptor, detect 429 → show toast "Too many requests, please wait X seconds" with `Retry-After` header value.

### PR-23: Missing Environment Variable Validation at Startup
**Branch**: `fix/medium-core-env-var-startup-validation`
**Fix**: Add `validate_required_settings()` call in app lifespan. Fail immediately with clear message listing missing vars.

---

## Phase 4 — Low (11 PRs)

### PR-24: Inconsistent Error Response Shapes
**Branch**: `fix/low-api-consistent-error-response`
**Fix**: Define `ErrorResponse(detail: str, code: str | None)` Pydantic model. Use consistently across all endpoints.

### PR-25: JWT Expiry Not Handled in Frontend
**Branch**: `fix/low-frontend-jwt-expiry-handling`
**Fix**: Decode JWT payload on login to extract `exp`. Set `setTimeout` to auto-logout 60s before expiry.

### PR-26: System Messages Not Internationalized
**Branch**: `fix/low-core-i18n-system-messages`
**Fix**: Read `Accept-Language` header in `deps.py`. Pass locale to system prompt builder. Add EN/ZH variants for system prompts.

### PR-27: Structured Logging Field Names Inconsistent
**Branch**: `fix/low-core-structured-logging-standard`
**Fix**: Create `backend/app/core/log_fields.py` with standard field name constants. Replace ad-hoc strings across all log calls.

### PR-28: No Database Query Timeout
**Branch**: `fix/low-db-query-timeout`
**Fix**: Add `connect_args={"command_timeout": 30}` to engine creation. Document in config.

### PR-29: Frontend Bundle Size Not Optimized
**Branch**: `fix/low-frontend-build-optimization`
**Fix**:
- Run `bun run build` and `bun run preview` to generate baseline bundle report
- Enable `vite-plugin-visualizer` (add as dev dep) to identify largest chunks
- Enable manual chunk splitting for large dependencies (`vue`, `axios`, `vue-i18n`) in `vite.config.ts` `build.rollupOptions.output.manualChunks`
- Verify initial JS bundle (excluding lazy-loaded routes) is under 200KB gzipped

**Acceptance criteria**: `bun run build` succeeds, `dist/assets/index-*.js` is ≤ 200KB gzipped (checked via `gzip -c file | wc -c`), and no single chunk exceeds 500KB ungzipped.

### PR-30: Agent Supervisor Route Not Validated
**Branch**: `fix/low-agent-supervisor-route-validation`
**Fix**: Define `AgentRoute = Literal["code", "research", "writing", "default"]` enum. Validate supervisor output before routing.

### PR-31: No Per-User API Key Creation Limit
**Branch**: `fix/low-api-key-creation-rate-limit`
**Fix**: Add `MAX_API_KEYS_PER_USER = 20` to config. Check count before creation in `POST /api/keys`.

### PR-32: Webhook Retry Without Backoff or Max Attempts
**Branch**: `fix/low-worker-webhook-retry-backoff`
**Fix**: Add `MAX_WEBHOOK_RETRIES = 10` to config. Use `2 ** (attempt - 1)` second delay. Mark delivery as permanently failed after max.

### PR-33: Non-Streaming Responses Not Compressed
**Branch**: `fix/low-api-response-compression`
**Fix**: Add `GZipMiddleware` to FastAPI app with `minimum_size=500`, but **exclude SSE routes** (`/api/chat/stream`, `/api/gateway/stream`) — GZip buffers chunks which breaks real-time SSE delivery. Apply compression only to JSON responses (admin, documents, settings, etc.). Verify in browser DevTools that JSON list responses are gzip-encoded and SSE streams are not affected.

### PR-34: Title Generation Has No Fallback
**Branch**: `fix/low-agent-title-generation-fallback`
**Fix**: Wrap title generation in `try/except`. Fall back to first 50 chars of user message on failure. Log failure with context.

### PR-35: No Limit on API Keys Per User (cleanup)
**Branch**: merged into PR-31 — see PR-31 above.
**Note**: PR-35 is consolidated with PR-31 since they address the same constraint. Total becomes 34 independent PRs.

---

## Testing Standards

| Issue Type | Required Tests |
|------------|---------------|
| Security fixes | Attack scenario test (prove vulnerability existed, prove it's fixed) |
| DB model changes | Migration test + model constraint test |
| API endpoint fixes | HTTP status code tests (happy path + error cases) |
| Frontend fixes | Component behavior test or E2E spec |
| Config/startup fixes | Startup failure test with missing/invalid config |

---

## Definition of Done

A PR is considered complete when:
1. Failing test committed alongside fix
2. All tests pass (`pytest tests/ -v`)
3. `ruff check`, `ruff format`, `mypy app` all clean (backend)
4. `bun run lint:fix`, `bun run type-check` clean (frontend)
5. `/simplify` has run and no remaining issues
6. `superpowers:code-reviewer` has approved
7. PR merged to `dev`

---

## Consolidated PR Count

- Phase 1 Critical: 4 PRs
- Phase 2 High: 8 PRs
- Phase 3 Medium: 11 PRs
- Phase 4 Low: 11 PRs (original PR-35 merged into PR-31)
- **Total: 34 PRs**
