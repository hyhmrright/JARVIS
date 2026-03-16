# Security & Quality Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 25 issues identified in the comprehensive code review, covering security vulnerabilities, data integrity bugs, and code quality problems.

**Architecture:** Fixes are organized into 7 independent task groups that can be executed in parallel. Each task modifies a small, focused set of files. No new migrations are needed — the IMAP encryption fix stores encrypted data in the existing `trigger_metadata` JSONB column.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, Vue 3 + TypeScript, Pinia, Python 3.13, cryptography (Fernet, already a dependency via `app.core.security`)

---

## Chunk 1: Security Critical — Backend API Schemas & SSRF

### Task 1: Fix SSRF Protection in `web_fetch_tool.py`

Issues #1 (Critical): Missing cloud metadata endpoints and IPv6 loopback in blocklist.

**Files:**
- Modify: `backend/app/tools/web_fetch_tool.py`
- Test: `backend/tests/tools/test_web_fetch_tool.py`

- [ ] **Step 1: Read test file to understand current coverage**

Run: `cat backend/tests/tools/test_web_fetch_tool.py`

- [ ] **Step 2: Update `_BLOCKED_HOSTS` and add metadata IP check**

In `backend/app/tools/web_fetch_tool.py`, replace:

```python
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}


def is_safe_url(url: str) -> bool:
    """Reject URLs targeting internal/private networks (SSRF protection)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname or ""
    if hostname in _BLOCKED_HOSTS:
        return False
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return False
    except ValueError:
        pass  # Not an IP literal — hostname is fine
    return True
```

with:

```python
_BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "[::1]",
    "::1",
    "metadata.google.internal",
    "169.254.169.254",   # AWS/GCP/Azure IMDS
    "100.100.100.200",   # Alibaba Cloud metadata
}


def is_safe_url(url: str) -> bool:
    """Reject URLs targeting internal/private networks (SSRF protection)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname or ""
    if hostname.lower() in _BLOCKED_HOSTS:
        return False
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return False
    except ValueError:
        pass  # Not an IP literal — hostname will be resolved by httpx
    return True
```

- [ ] **Step 3: Verify test still passes (read test, confirm coverage includes new hosts)**

Check that test file covers `169.254.169.254` and `metadata.google.internal`. If not, note it — we can't run tests locally but the logic is straightforward.

- [ ] **Step 4: Run static checks**

```bash
cd backend && uv run ruff check --fix app/tools/web_fetch_tool.py && uv run ruff format app/tools/web_fetch_tool.py
```

---

### Task 2: Add Pydantic Schema to `cron.py` (Issue #3 Critical)

**Files:**
- Modify: `backend/app/api/cron.py`
- Test: `backend/tests/scheduler/test_cron.py` (read to verify patch targets)

- [ ] **Step 1: Add Pydantic schema and update endpoint**

In `backend/app/api/cron.py`, replace the imports and `create_cron_job` function:

```python
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import CronJob, User
from app.db.session import get_db
from app.scheduler.runner import register_cron_job, unregister_cron_job

router = APIRouter(prefix="/api/cron", tags=["cron"])

_VALID_TRIGGER_TYPES = {"cron", "web_watcher", "semantic_watcher", "email"}


class CronJobCreate(BaseModel):
    schedule: str = Field(min_length=1, max_length=100)
    task: str = Field(min_length=1, max_length=4000)
    trigger_type: str = Field(default="cron", max_length=50)
    trigger_metadata: dict[str, Any] | None = None
```

Then update `create_cron_job`:

```python
@router.post("")
async def create_cron_job(
    data: CronJobCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Create a new proactive monitoring job."""
    if data.trigger_type not in _VALID_TRIGGER_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid trigger_type. Must be one of: {sorted(_VALID_TRIGGER_TYPES)}")
    job = CronJob(
        user_id=user.id,
        schedule=data.schedule,
        task=data.task,
        trigger_type=data.trigger_type,
        trigger_metadata=data.trigger_metadata,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    if job.is_active:
        register_cron_job(str(job.id), str(user.id), job.schedule, job.task)

    return {"status": "ok", "id": str(job.id)}
```

- [ ] **Step 2: Run static checks**

```bash
cd backend && uv run ruff check --fix app/api/cron.py && uv run ruff format app/api/cron.py && uv run mypy app/api/cron.py
```

---

### Task 3: Add Pydantic Schema + Self-Demotion Guard to `admin.py` (Issue #4 Critical, #17 Suggestion)

**Files:**
- Modify: `backend/app/api/admin.py`

- [ ] **Step 1: Add schema and guards**

Replace imports and `update_user` in `backend/app/api/admin.py`:

```python
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user
from app.db.models import AuditLog, Conversation, Message, User, UserRole
from app.db.session import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
```

Replace `update_user` and `delete_user`:

```python
@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict[str, str]:
    """Update user role or status."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own account")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.role is not None:
        if data.role not in [r.value for r in UserRole]:
            raise HTTPException(status_code=400, detail="Invalid role")
        if (
            user.role in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value)
            and admin.role != UserRole.SUPERADMIN.value
        ):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        user.role = data.role

    if data.is_active is not None:
        user.is_active = data.is_active

    await db.commit()
    return {"status": "ok"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict[str, str]:
    """Soft-delete a user."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if admin.role != UserRole.SUPERADMIN.value and user.role != UserRole.USER.value:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    user.is_active = False
    await db.commit()
    return {"status": "ok"}
```

- [ ] **Step 2: Run static checks**

```bash
cd backend && uv run ruff check --fix app/api/admin.py && uv run ruff format app/api/admin.py && uv run mypy app/api/admin.py
```

---

## Chunk 2: Dead Code, Type Safety & Rate Limiting

### Task 4: Remove Dead Code `docker_executor.py` (Issue #5 Critical, #20 Suggestion)

**Files:**
- Delete: `backend/app/sandbox/docker_executor.py`

- [ ] **Step 1: Verify no imports of DockerSandbox in production code**

```bash
grep -r "DockerSandbox\|docker_executor" backend/app/ --include="*.py"
```

Expected: no results (only the file itself).

- [ ] **Step 2: Delete the file**

```bash
rm backend/app/sandbox/docker_executor.py
```

- [ ] **Step 3: Check tests reference**

```bash
grep -r "docker_executor\|DockerSandbox" backend/tests/ --include="*.py"
```

If any test imports it, remove those test cases too.

- [ ] **Step 4: Verify collect-only still passes**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```

---

### Task 5: Fix Type Annotations in `deps.py` (Issue #9 Important)

**Files:**
- Modify: `backend/app/api/deps.py`

- [ ] **Step 1: Fix `request` parameter type annotations**

In `backend/app/api/deps.py`, replace:

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
) -> User:
```

with:

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    request: Request | None = None,
) -> User:
```

And:

```python
async def get_current_user_query_token(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
) -> User:
```

with:

```python
async def get_current_user_query_token(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    request: Request | None = None,
) -> User:
```

- [ ] **Step 2: Run mypy to confirm fix**

```bash
cd backend && uv run mypy app/api/deps.py
```

Expected: no errors on these lines.

---

### Task 6: Fix Rate Limiter PAT Support (Issue #7 Important, #16 Suggestion)

**Files:**
- Modify: `backend/app/core/limiter.py`

The PAT token starts with `jv_`. We need to extract user ID from PAT via DB lookup — but that's expensive per request. A simpler approach: use a deterministic hash of the PAT token itself as the rate-limit key (so it's per-key, not per-IP), with a `pat:` prefix to distinguish from JWT users.

- [ ] **Step 1: Update `_get_user_or_ip` to handle PAT tokens**

Replace `backend/app/core/limiter.py` content:

```python
import hashlib

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_user_or_ip(request: Request) -> str:
    """Per-user key for authenticated requests; fall back to IP for anonymous.

    For JWT tokens: decodes the Bearer token to obtain the user ID.
    For PAT tokens (jv_*): uses a hash of the token itself as the key,
    ensuring per-key (and thus per-user) rate limiting without a DB lookup.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        if token.startswith("jv_"):
            # PAT: use hash of token as stable per-key identifier
            token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
            return f"pat:{token_hash}"
        try:
            from app.core.security import decode_access_token

            user_id = decode_access_token(token)
            return f"user:{user_id}"
        except Exception:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_get_user_or_ip)
```

- [ ] **Step 2: Run static checks**

```bash
cd backend && uv run ruff check --fix app/core/limiter.py && uv run ruff format app/core/limiter.py && uv run mypy app/core/limiter.py
```

---

### Task 7: Add Rate Limiting to Webhook Trigger (Issue #10 Important)

**Files:**
- Modify: `backend/app/api/webhooks.py`

- [ ] **Step 1: Import limiter and add decorator**

In `backend/app/api/webhooks.py`, add import after existing imports:

```python
from app.core.limiter import limiter
```

Then add rate limit decorator to `trigger_webhook`:

```python
@router.post("/{webhook_id}/trigger", status_code=202)
@limiter.limit("30/minute")
async def trigger_webhook(
    webhook_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
```

- [ ] **Step 2: Run static checks**

```bash
cd backend && uv run ruff check --fix app/api/webhooks.py && uv run ruff format app/api/webhooks.py && uv run mypy app/api/webhooks.py
```

---

## Chunk 3: Data Integrity & Agent Fixes

### Task 8: Fix Message Ordering in `agent_runner.py` (Issue #6 Important)

**Files:**
- Modify: `backend/app/gateway/agent_runner.py`

The human message must be flushed to DB **before** the agent is invoked so the timestamp precedes the AI message.

- [ ] **Step 1: Reorder DB operations**

In `backend/app/gateway/agent_runner.py`, replace lines 50-96 (the section from `conv = Conversation(...)` to `await db.commit()`):

```python
            conv = Conversation(
                user_id=uuid.UUID(user_id),
                title=f"Auto: {task[:60]}",
            )
            db.add(conv)
            # Persist human message BEFORE invoking agent so its timestamp
            # precedes the AI message in chronological ordering.
            human_msg = Message(conversation_id=conv.id, role="human", content=task)
            db.add(human_msg)
            await db.flush()

            lc_messages = [
                SystemMessage(content=build_system_prompt(persona)),
                HumanMessage(content=task),
            ]

            mcp_tools: list = []
            if "mcp" in enabled:
                from app.tools.mcp_client import create_mcp_tools, parse_mcp_configs

                mcp_tools = await create_mcp_tools(
                    parse_mcp_configs(settings.mcp_servers_json)
                )

            graph = create_graph(
                provider=provider,
                model=model_name,
                api_key=api_keys[0],
                enabled_tools=enabled,
                api_keys=api_keys,
                user_id=user_id,
                openai_api_key=resolve_api_key("openai", raw_keys),
                tavily_api_key=settings.tavily_api_key,
                mcp_tools=mcp_tools,
                conversation_id=str(conv.id),
            )

            result = await graph.ainvoke(AgentState(messages=lc_messages))
            ai_content = str(result["messages"][-1].content)

            db.add(
                Message(
                    conversation_id=conv.id,
                    role="ai",
                    content=ai_content,
                    model_provider=provider,
                    model_name=model_name,
                )
            )
            await db.commit()
```

- [ ] **Step 2: Run static checks**

```bash
cd backend && uv run ruff check --fix app/gateway/agent_runner.py && uv run ruff format app/gateway/agent_runner.py && uv run mypy app/gateway/agent_runner.py
```

---

### Task 9: Fix YAML Injection + UUID Collision in `memory_sync.py` (Issues #8 Important, #22 Suggestion)

**Files:**
- Modify: `backend/app/services/memory_sync.py`

- [ ] **Step 1: Fix YAML frontmatter and use full UUID for filename**

In `backend/app/services/memory_sync.py`, replace the frontmatter building and filename sections:

```python
            # File naming: date-full_uuid.md (avoid truncation collisions)
            date_str = conv.created_at.strftime("%Y-%m-%d")
            file_path = sync_dir / f"{date_str}-{conversation_id}.md"

            lines = []
            # YAML Frontmatter — quote string fields to prevent injection
            lines.append("---")
            lines.append(f"title: {_yaml_quote(conv.title)}")
            lines.append(f"id: {conversation_id}")
            lines.append(f"date: {conv.created_at.isoformat()!r}")
            lines.append(f"updated: {conv.updated_at.isoformat()!r}")
            lines.append("tags: [jarvis, memory]")
            lines.append("---\n")
```

And add the helper function near the top (after imports):

```python
def _yaml_quote(value: str) -> str:
    """Return a single-quoted YAML string, escaping single quotes within."""
    escaped = value.replace("'", "''")
    return f"'{escaped}'"
```

- [ ] **Step 2: Run static checks**

```bash
cd backend && uv run ruff check --fix app/services/memory_sync.py && uv run ruff format app/services/memory_sync.py && uv run mypy app/services/memory_sync.py
```

---

### Task 10: Fix `SemanticWatcherProcessor` Settings + IMAP Password Encryption (Issues #11 Important, #24 Suggestion)

**Files:**
- Modify: `backend/app/scheduler/triggers.py`

**Sub-issue A — SemanticWatcherProcessor uses wrong settings attributes:**

`settings` doesn't have `model_provider` or `model_name`. Use the server-level keys directly with explicit fallback logic.

**Sub-issue B — IMAP password stored in plaintext:**

Use Fernet encryption (same as LLM API keys) when storing/reading IMAP credentials. The encryption key is `settings.secret_key` (via `app.core.security.fernet`).

- [ ] **Step 1: Fix SemanticWatcherProcessor to use server-level keys properly**

In `backend/app/scheduler/triggers.py`, replace lines 78-85:

```python
            # Use server-level LLM keys for semantic checking.
            # Priority: deepseek > openai (whichever has a key configured).
            if settings.deepseek_api_key:
                provider = "deepseek"
                model = "deepseek-chat"
                api_key = settings.deepseek_api_key
            elif settings.openai_api_key:
                provider = "openai"
                model = "gpt-4o-mini"
                api_key = settings.openai_api_key
            else:
                logger.error("semantic_watcher_no_api_key")
                return False

            llm = get_llm_with_fallback(provider, model, api_key)
```

- [ ] **Step 2: Encrypt/decrypt IMAP password in `IMAPEmailProcessor`**

Add import at top of file (after existing imports):

```python
from app.core.security import fernet_decrypt, fernet_encrypt
```

Then in `IMAPEmailProcessor.should_fire`, replace:

```python
        password = metadata.get("imap_password")
        if not all([host, user, password]):
            return False
```

with:

```python
        password_encrypted = metadata.get("imap_password")
        if not all([host, user, password_encrypted]):
            return False
        try:
            password = fernet_decrypt(str(password_encrypted))
        except Exception:
            logger.error("imap_password_decrypt_failed", user=user)
            return False
```

- [ ] **Step 3: Check that `fernet_encrypt` and `fernet_decrypt` exist in security module**

```bash
grep -n "def fernet_encrypt\|def fernet_decrypt" backend/app/core/security.py
```

If they don't exist, add them. Read `backend/app/core/security.py` first and add:

```python
def fernet_encrypt(value: str) -> str:
    """Encrypt a string value using the app's Fernet key."""
    return _fernet.encrypt(value.encode()).decode()


def fernet_decrypt(value: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    return _fernet.decrypt(value.encode()).decode()
```

(Check the existing Fernet instance name in security.py before adding.)

- [ ] **Step 4: Run static checks**

```bash
cd backend && uv run ruff check --fix app/scheduler/triggers.py app/core/security.py && uv run ruff format app/scheduler/triggers.py app/core/security.py && uv run mypy app/scheduler/triggers.py
```

---

### Task 11: Initialize Workspace in `file_tool.py` (Issue #12 Important)

**Files:**
- Modify: `backend/app/tools/file_tool.py`
- Test: `backend/tests/tools/test_file_tool.py` (read to verify)

- [ ] **Step 1: Create workspace at tool creation time and add /tmp warning**

In `backend/app/tools/file_tool.py`, replace:

```python
def create_file_tools(user_id: str) -> list[BaseTool]:  # noqa: C901
    """Create file operation tools scoped to a user's workspace."""
    workspace = pathlib.Path(f"/tmp/jarvis/{user_id}")
```

with:

```python
def create_file_tools(user_id: str) -> list[BaseTool]:  # noqa: C901
    """Create file operation tools scoped to a user's workspace.

    Note: workspace lives under /tmp which is not persistent across
    container restarts. Files will be lost on restart.
    """
    workspace = pathlib.Path(f"/tmp/jarvis/{user_id}")
    workspace.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: Run static checks**

```bash
cd backend && uv run ruff check --fix app/tools/file_tool.py && uv run ruff format app/tools/file_tool.py && uv run mypy app/tools/file_tool.py
```

---

## Chunk 4: Shell Tool, Chat & Agent Quality

### Task 12: Improve Shell Tool Blocklist (Issue #2 Critical)

**Files:**
- Modify: `backend/app/tools/shell_tool.py`

Note: The sandbox is the primary security boundary. The blocklist is best-effort but should cover more dangerous patterns.

- [ ] **Step 1: Expand `_BLOCKED_PATTERNS`**

In `backend/app/tools/shell_tool.py`, replace:

```python
_BLOCKED_PATTERNS: set[str] = {
    "rm -rf /",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
    "chmod -R 777 /",
    ">(){ ",
    "fork bomb",
}
```

with:

```python
# Best-effort filter — the Docker sandbox is the primary security boundary.
# When sandbox_enabled=False (local exec inside backend container), these
# patterns reduce accidental damage. They are NOT a substitute for sandboxing.
_BLOCKED_PATTERNS: set[str] = {
    "rm -rf /",
    "rm -rf /*",
    "rm --no-preserve-root",
    "mkfs",
    "dd if=",
    "dd of=/dev/",
    ":(){:|:&};:",
    "chmod -R 777 /",
    ">(){ ",
    "fork bomb",
    "/dev/sda",
    "/dev/sdb",
    "/dev/nvme",
    "shred /dev/",
    "> /dev/",
}
```

- [ ] **Step 2: Run static checks**

```bash
cd backend && uv run ruff check --fix app/tools/shell_tool.py && uv run ruff format app/tools/shell_tool.py
```

---

### Task 13: Log Dropped Messages in `chat.py` (Issue #15 Suggestion)

**Files:**
- Modify: `backend/app/api/chat.py`

- [ ] **Step 1: Find and update the message filtering code**

In `backend/app/api/chat.py`, find:

```python
    lc_messages = [
        _ROLE_TO_MESSAGE[msg.role](content=msg.content)
        for msg in history_rows.all()
        if msg.role in _ROLE_TO_MESSAGE
    ]
```

Replace with:

```python
    all_history = history_rows.all()
    lc_messages = []
    for msg in all_history:
        if msg.role in _ROLE_TO_MESSAGE:
            lc_messages.append(_ROLE_TO_MESSAGE[msg.role](content=msg.content))
        else:
            logger.debug(
                "chat_history_message_skipped",
                role=msg.role,
                msg_id=str(msg.id),
            )
```

- [ ] **Step 2: Run static checks**

```bash
cd backend && uv run ruff check --fix app/api/chat.py && uv run ruff format app/api/chat.py && uv run mypy app/api/chat.py
```

---

### Task 14: Fix Compressor Character Count (Issue #21 Suggestion)

**Files:**
- Modify: `backend/app/agent/compressor.py`

- [ ] **Step 1: Update total_chars calculation to include type prefix**

In `backend/app/agent/compressor.py`, replace:

```python
    total_chars = sum(len(str(m.content)) for m in messages)
```

with:

```python
    total_chars = sum(len(f"{m.type}: {m.content}") for m in messages)
```

- [ ] **Step 2: Run static checks**

```bash
cd backend && uv run ruff check --fix app/agent/compressor.py && uv run ruff format app/agent/compressor.py && uv run mypy app/agent/compressor.py
```

---

## Chunk 5: Frontend Fixes

### Task 15: Use Pinia Auth Store Token in `chat.ts` (Issue #18 Suggestion)

**Files:**
- Modify: `frontend/src/stores/chat.ts`

- [ ] **Step 1: Import and use auth store**

In `frontend/src/stores/chat.ts`, add import at top:

```typescript
import { useAuthStore } from "@/stores/auth";
```

Then in `sendMessage`, replace:

```typescript
        const token = localStorage.getItem("token");
```

with:

```typescript
        const auth = useAuthStore();
        const token = auth.token;
```

- [ ] **Step 2: Run frontend lint**

```bash
cd frontend && bun run lint:fix && bun run type-check
```

---

### Task 16: Add Catch-All Route to Router (Issue #23 Suggestion)

**Files:**
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Add catch-all route**

In `frontend/src/router/index.ts`, add to the `routes` array before the closing bracket:

```typescript
    { path: "/:pathMatch(.*)*", redirect: "/" },
```

- [ ] **Step 2: Run frontend lint**

```bash
cd frontend && bun run lint:fix && bun run type-check
```

---

## Chunk 6: JWT Default Expiry (Issue #19 Suggestion)

### Task 17: Reduce JWT Default Expiry from 30 to 7 Days

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Find and update JWT expiry default**

```bash
grep -n "jwt_expire_minutes" backend/app/core/config.py
```

Replace:

```python
    jwt_expire_minutes: int = 60 * 24 * 30  # 30 days
```

with:

```python
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days
```

- [ ] **Step 2: Run static checks**

```bash
cd backend && uv run ruff check --fix app/core/config.py && uv run ruff format app/core/config.py
```

---

## Final: Verification

### Task 18: Full Static Check & Collect-Only Verification

- [ ] **Step 1: Run full backend static checks**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
```

- [ ] **Step 2: Verify FastAPI import check passes**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -10
```

Expected: all tests collected, no import errors.

- [ ] **Step 3: Run frontend checks**

```bash
cd frontend && bun run lint:fix && bun run type-check
```

- [ ] **Step 4: Commit all changes**

```bash
git add -A
git commit -m "fix: address all code review issues — security, data integrity, quality"
```
