# Phase 16: Critical Bug Sweep + Infrastructure Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all Critical-severity functional breakage and harden database/Docker infrastructure.

**Architecture:** Six independent fix targets: frontend folder API paths, agent approval graph edge, webhook secret encryption, missing DB indexes, Docker resource limits/healthchecks, and two frontend minor fixes. Each task is self-contained with its own tests and commit.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy / Alembic / Vue 3 / TypeScript / Docker Compose

**Spec:** `docs/superpowers/specs/2026-03-25-phase16-20-comprehensive-upgrade-design.md` (sections 16.1–16.6)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/src/stores/chat.ts` | Fix 4 double-prefix folder API paths + rethrow deleteConversation error |
| Modify | `backend/app/agent/graph.py` | Add missing approval→END edge |
| Modify | `backend/app/db/models.py` | Add `index=True` to 3 FK columns; update Webhook model column length for encrypted values |
| Modify | `backend/app/api/webhooks.py` | Import and use `fernet_encrypt`/`fernet_decrypt` for secret_token |
| Create | `backend/alembic/versions/xxxx_phase16_indexes_and_webhook_encryption.py` | Migration: add indexes + batch-encrypt webhook secrets |
| Modify | `docker-compose.yml` | Resource limits, worker healthcheck, backend healthcheck DB ping |
| Modify | `frontend/src/pages/AdminPage.vue` | Fix plugin toggle checked binding |

---

### Task 1: Fix Frontend Folder Store Double-Prefix Bug

**Files:**
- Modify: `frontend/src/stores/chat.ts:145,153,163,173` (4 lines)

- [ ] **Step 1: Fix the four `/api/folders` paths to `/folders`**

In `frontend/src/stores/chat.ts`, change the four folder API calls. The Axios `client` already has `baseURL: "/api"`, so these paths should NOT include `/api`.

Note: The spec mentions 5 lines (144/153/163/172/186), but line 186 (`client.patch(`/conversations/${convId}`, ...)`) uses the correct `/conversations/` path — it is NOT a folder call and has no bug. Only the 4 lines below need fixing.

Line 145 — `loadFolders`:
```ts
// BEFORE:
const { data } = await client.get<Folder[]>("/api/folders");
// AFTER:
const { data } = await client.get<Folder[]>("/folders");
```

Line 153 — `createFolder`:
```ts
// BEFORE:
const { data } = await client.post<Folder>("/api/folders", { name, color });
// AFTER:
const { data } = await client.post<Folder>("/folders", { name, color });
```

Line 163 — `updateFolder`:
```ts
// BEFORE:
const { data } = await client.patch<Folder>(`/api/folders/${folderId}`, updates);
// AFTER:
const { data } = await client.patch<Folder>(`/folders/${folderId}`, updates);
```

Line 173 — `deleteFolder`:
```ts
// BEFORE:
await client.delete(`/api/folders/${folderId}`);
// AFTER:
await client.delete(`/folders/${folderId}`);
```

- [ ] **Step 2: Verify no other double-prefix paths exist**

Run: `grep -n '"/api/' frontend/src/stores/chat.ts`

Expected: No results (all API paths in stores should be relative to `/api` baseURL).

- [ ] **Step 3: Run frontend type check**

Run: `cd frontend && bun run type-check`

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/chat.ts
git commit -m "fix: remove double /api/ prefix in folder store API calls"
```

---

### Task 2: Fix Frontend deleteConversation Error Swallowing + AdminPage Plugin Toggle

**Files:**
- Modify: `frontend/src/stores/chat.ts:231-245`
- Modify: `frontend/src/pages/AdminPage.vue:88`

- [ ] **Step 1: Make deleteConversation rethrow errors**

In `frontend/src/stores/chat.ts`, the `deleteConversation` method (lines 231–245) catches and swallows errors. Change the catch block to rethrow:

```ts
// BEFORE (line 243-244):
  } catch (err) {
    console.error("[chat] deleteConversation failed", err);
  }

// AFTER:
  } catch (err) {
    console.error("[chat] deleteConversation failed", err);
    throw err;
  }
```

- [ ] **Step 2: Fix AdminPage plugin toggle checked binding**

In `frontend/src/pages/AdminPage.vue` line 88, the `checked` attribute is hardcoded. The backend `PluginInfo` schema has no `is_enabled` field — plugins in the list are always "available" (loaded in registry). The toggle calls `POST /plugins/{id}/enable` which does not exist in the backend.

**Scoped fix (UI only, backend endpoint is out of scope for Phase 16):** Remove the non-functional toggle entirely and replace with a static "Active" badge, since all listed plugins are active by definition (they are loaded in the registry).

```html
<!-- BEFORE (lines 86-91): -->
<div class="plugin-ctrl">
  <label class="switch">
    <input type="checkbox" checked @change="togglePlugin(plugin.id, ($event.target as HTMLInputElement).checked)" />
    <span class="slider round"></span>
  </label>
</div>

<!-- AFTER: -->
<div class="plugin-ctrl">
  <span class="stat-pill">{{ $t('admin.plugins.active') }}</span>
</div>
```

Add the i18n key to `frontend/src/locales/en.json` and `zh.json`:
- en: `"admin.plugins.active": "Active"`
- zh: `"admin.plugins.active": "已启用"`

- [ ] **Step 3: Run frontend type check + lint**

Run: `cd frontend && bun run type-check && bun run lint`

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/chat.ts frontend/src/pages/AdminPage.vue frontend/src/locales/en.json frontend/src/locales/zh.json
git commit -m "fix: rethrow deleteConversation error, replace broken plugin toggle with badge"
```

---

### Task 3: Fix Agent Approval Node Dead End

**Files:**
- Modify: `backend/app/agent/graph.py:224` (add one line after existing edges)

- [ ] **Step 1: Add the missing approval→END edge**

In `backend/app/agent/graph.py`, after the existing edges (line 224: `graph.add_edge("review", END)`), add:

```python
# BEFORE (lines 223-224):
graph.add_edge("tools", "llm")
graph.add_edge("review", END)

# AFTER:
graph.add_edge("tools", "llm")
graph.add_edge("review", END)
graph.add_edge("approval", END)
```

The approval node writes `pending_tool_call` to state, then the graph ends. The SSE stream emits an `approval_required` event. When the user responds with `[CONSENT:ALLOW]` or `[CONSENT:DENY]`, `chat.py` creates a new graph invocation with the `approved` field set, and the `post_llm_route` conditional edge (lines 206-216) routes accordingly:
- `approved=True` → `"tools"` (execute the tool)
- `approved=False` → `END` (reject)

- [ ] **Step 2: Verify the graph compiles**

Run: `cd backend && uv run python -c "from app.agent.graph import create_graph; print('OK')"`

Expected: `OK` (no compilation error).

- [ ] **Step 3: Run backend lint + type check**

Run: `cd backend && uv run ruff check app/agent/graph.py && uv run mypy app/agent/graph.py`

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent/graph.py
git commit -m "fix: add missing approval→END edge in agent graph"
```

---

### Task 4: Encrypt Webhook Secret Tokens

**Files:**
- Modify: `backend/app/api/webhooks.py:1,61,124-126` (imports + encrypt on create + decrypt on verify)
- Modify: `backend/app/db/models.py:474` (increase column length for encrypted values)

- [ ] **Step 1: Increase secret_token column length in model**

Fernet-encrypted values are longer than the original plaintext. In `backend/app/db/models.py` line 474:

```python
# BEFORE:
secret_token: Mapped[str] = mapped_column(String(255), nullable=False)

# AFTER:
secret_token: Mapped[str] = mapped_column(String(500), nullable=False)
```

- [ ] **Step 2: Add encryption to webhook creation**

In `backend/app/api/webhooks.py`, add the import and encrypt on creation:

```python
# Add to imports at top of file:
from app.core.security import fernet_encrypt, fernet_decrypt
```

At the webhook creation point (line 61), encrypt before storing:

```python
# BEFORE:
secret_token=secrets.token_urlsafe(32),

# AFTER:
secret_token=fernet_encrypt(secrets.token_urlsafe(32)),
```

- [ ] **Step 3: Add decryption to webhook verification**

In `backend/app/api/webhooks.py` lines 124-126, decrypt before comparing:

```python
# BEFORE:
provided = request.headers.get("X-Webhook-Secret", "")
if not hmac.compare_digest(provided, webhook.secret_token):
    raise HTTPException(status_code=401, detail="Invalid webhook secret")

# AFTER:
provided = request.headers.get("X-Webhook-Secret", "")
try:
    decrypted = fernet_decrypt(webhook.secret_token)
except Exception:
    raise HTTPException(status_code=500, detail="Failed to decrypt webhook secret")
if not hmac.compare_digest(provided, decrypted):
    raise HTTPException(status_code=401, detail="Invalid webhook secret")
```

- [ ] **Step 4: Return secret only on creation, mask in list responses**

**Decision: Show plaintext secret_token only at creation time.** This is the industry-standard pattern (like GitHub tokens). List responses mask the value.

Create a new `WebhookCreateOut` schema for the creation response, and modify `WebhookOut` for list responses:

```python
# In webhooks.py, add a new schema after WebhookOut:
class WebhookCreateOut(WebhookOut):
    """Returned only on creation — includes the plaintext secret."""
    secret_token: str  # plaintext, shown only once

# Modify WebhookOut to mask the secret:
class WebhookOut(BaseModel):
    id: uuid.UUID
    name: str
    task_template: str
    secret_token: str = "••••••••"  # masked in list responses
    trigger_count: int
    is_active: bool
    last_triggered_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

Update `create_webhook` (line 50-67):
```python
@router.post("", status_code=201, response_model=WebhookCreateOut)
async def create_webhook(...) -> WebhookCreateOut:
    raw_secret = secrets.token_urlsafe(32)
    webhook = Webhook(
        user_id=user.id,
        name=body.name,
        task_template=body.task_template,
        secret_token=fernet_encrypt(raw_secret),
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    logger.info("webhook_created", user_id=str(user.id), webhook_id=str(webhook.id))
    # Return with plaintext secret (shown only once)
    out = WebhookCreateOut.model_validate(webhook)
    out.secret_token = raw_secret
    return out
```

`list_webhooks` (line 70-84) needs no change — `WebhookOut.secret_token` defaults to `"••••••••"` and the encrypted DB value is never exposed.

- [ ] **Step 5: Run backend lint + type check**

Run: `cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app/api/webhooks.py app/db/models.py`

Expected: No errors.

- [ ] **Step 6: Run existing webhook tests**

Run: `cd backend && uv run pytest tests/api/test_webhooks.py -v`

Expected: All tests pass (tests may need adjustment if they check `secret_token` value directly).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/webhooks.py backend/app/db/models.py
git commit -m "feat: encrypt webhook secret_token with Fernet"
```

---

### Task 5: Alembic Migration — Indexes + Webhook Secret Encryption

**Files:**
- Create: `backend/alembic/versions/phase16_indexes_and_webhook_encryption.py`

**down_revision**: `"b629655503d7"` (current HEAD: `add_notifications`)

- [ ] **Step 1: Generate migration skeleton**

Run: `cd backend && uv run alembic revision -m "phase16_indexes_and_webhook_encryption"`

- [ ] **Step 2: Write the migration**

```python
"""phase16_indexes_and_webhook_encryption

Revision ID: <auto-generated>
Revises: b629655503d7
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "<auto-generated>"
down_revision = "b629655503d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Add missing indexes ---
    op.create_index("ix_personas_user_id", "personas", ["user_id"])
    op.create_index("ix_workflows_user_id", "workflows", ["user_id"])
    op.create_index("ix_installed_plugins_installed_by", "installed_plugins", ["installed_by"])

    # --- Widen secret_token column for Fernet-encrypted values ---
    op.alter_column(
        "webhooks",
        "secret_token",
        type_=sa.String(500),
        existing_type=sa.String(255),
        existing_nullable=False,
    )

    # --- Batch-encrypt existing plaintext webhook secrets ---
    conn = op.get_bind()
    rows = conn.execute(text("SELECT id, secret_token FROM webhooks")).fetchall()
    if rows:
        from app.core.security import fernet_encrypt
        for row in rows:
            encrypted = fernet_encrypt(row.secret_token)
            conn.execute(
                text("UPDATE webhooks SET secret_token = :token WHERE id = :id"),
                {"token": encrypted, "id": row.id},
            )


def downgrade() -> None:
    # --- Batch-decrypt webhook secrets back to plaintext ---
    conn = op.get_bind()
    rows = conn.execute(text("SELECT id, secret_token FROM webhooks")).fetchall()
    if rows:
        from app.core.security import fernet_decrypt
        for row in rows:
            try:
                decrypted = fernet_decrypt(row.secret_token)
                conn.execute(
                    text("UPDATE webhooks SET secret_token = :token WHERE id = :id"),
                    {"token": decrypted, "id": row.id},
                )
            except Exception:
                pass  # Already plaintext (idempotent)

    op.alter_column(
        "webhooks",
        "secret_token",
        type_=sa.String(255),
        existing_type=sa.String(500),
        existing_nullable=False,
    )

    op.drop_index("ix_installed_plugins_installed_by", "installed_plugins")
    op.drop_index("ix_workflows_user_id", "workflows")
    op.drop_index("ix_personas_user_id", "personas")
```

- [ ] **Step 3: Update models.py to add `index=True` annotations**

In `backend/app/db/models.py`:

Persona model (line 884-886) — add `index=True`:
```python
# BEFORE:
user_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
)

# AFTER:
user_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
)
```

Workflow model (line 903-905) — add `index=True`:
```python
# Same pattern: add index=True to the user_id mapped_column
```

InstalledPlugin model (line 982-986) — add `index=True`:
```python
# Same pattern: add index=True to the installed_by mapped_column
```

- [ ] **Step 4: Verify migration can run**

Run: `cd backend && uv run alembic upgrade head`

Expected: Migration applies successfully.

- [ ] **Step 5: Verify downgrade works**

Run: `cd backend && uv run alembic downgrade -1 && uv run alembic upgrade head`

Expected: Both succeed without errors.

- [ ] **Step 6: Run pytest collect to verify no import errors**

Run: `cd backend && uv run pytest --collect-only -q`

Expected: All tests collected, no import errors.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/ backend/app/db/models.py
git commit -m "feat: add missing indexes and batch-encrypt webhook secrets (migration)"
```

---

### Task 6: Docker Hardening

**Files:**
- Modify: `docker-compose.yml` (backend, worker, frontend services)

- [ ] **Step 1: Add resource limits to backend service**

In `docker-compose.yml`, inside the `backend` service block (after `healthcheck`), add:

```yaml
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
```

- [ ] **Step 2: Add resource limits to worker service**

In the `worker` service block, add:

```yaml
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
```

- [ ] **Step 3: Add healthcheck to worker service**

The worker connects to Redis for ARQ. Add a healthcheck that verifies Redis connectivity:

```yaml
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import redis, os; r = redis.from_url(os.environ.get('REDIS_URL', 'redis://redis:6379')); r.ping()\""]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

- [ ] **Step 4: Add resource limits to frontend service**

```yaml
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
```

- [ ] **Step 5: Enhance backend healthcheck to include DB ping**

Replace the existing backend healthcheck test (line 147) with one that also checks DB connectivity:

```yaml
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\" && python -c \"import asyncio, os; from sqlalchemy.ext.asyncio import create_async_engine; e = create_async_engine(os.environ['DATABASE_URL']); asyncio.run(e.dispose())\""]
      interval: 10s
      timeout: 10s
      retries: 10
      start_period: 120s
```

Note: If the DATABASE_URL construction is complex, a simpler approach is to add a `/health/db` endpoint in the backend that does a `SELECT 1` and check that from the healthcheck. However, that's a backend code change. For now, the HTTP health endpoint should be sufficient if the backend's lifespan already validates DB connectivity at startup.

**Simpler alternative:** Keep the existing HTTP healthcheck (which already validates the app is running), and rely on the `depends_on: postgres: condition: service_healthy` to ensure DB is available at startup. The HTTP check is adequate for runtime health.

Decision: Keep existing backend healthcheck as-is (HTTP only). Add resource limits and worker healthcheck only.

- [ ] **Step 6: Verify Docker Compose config is valid**

Run: `docker compose config --quiet`

Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml
git commit -m "infra: add resource limits and worker healthcheck to Docker services"
```

---

## Verification Checklist

After all tasks are complete, verify:

- [ ] `cd frontend && bun run type-check` — passes
- [ ] `cd frontend && bun run lint` — passes
- [ ] `cd backend && uv run ruff check && uv run ruff format --check` — passes
- [ ] `cd backend && uv run mypy app` — passes
- [ ] `cd backend && uv run pytest --collect-only -q` — all tests collected
- [ ] `cd backend && uv run pytest tests/ -v` — all existing tests pass
- [ ] `docker compose config --quiet` — valid config
- [ ] `grep -rn '"/api/' frontend/src/stores/chat.ts` — no results (no double prefix)
- [ ] `grep -n 'add_edge.*approval' backend/app/agent/graph.py` — shows approval→END edge

---

## Discovery Notes

During research for this plan, the following additional issues were found:

1. **Plugin enable/disable endpoint missing**: The frontend `AdminPage.vue` calls `POST /plugins/{id}/enable` via `adminApi.enablePlugin()`, but this route does not exist in `backend/app/api/plugins.py`. The `PluginInfo` schema has no `is_enabled` field. This is a deeper feature gap than a UI toggle fix — the entire plugin enable/disable feature is unimplemented. Tracked for Phase 19 or 20.

2. **`WorkflowRun.user_id` already has `index=True`**: The spec listed this as missing, but investigation confirmed it already exists (models.py lines 936-941). Removed from the migration.

3. **AuditLog redundant indexes**: The spec suggested removing single-column indexes on `audit_logs.user_id` and `audit_logs.action`. However, the composite index is defined only in a migration, not in the model's `__table_args__`. Dropping single-column indexes that the model declares (`index=True`) while the composite lives only in a migration creates a mismatch. Deferred to a future cleanup to avoid risk.

4. **Notification composite index**: Already created in migration `b629655503d7`. No need to recreate. Removed from the migration.
