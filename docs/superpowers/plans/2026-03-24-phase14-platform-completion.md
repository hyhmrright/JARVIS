# Phase 14: Platform Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 6 platform features: LLM parameter controls, conversation folders, file attachments, cost estimation, in-app notifications, and workflow execution engine.

**Architecture:** Each feature is independent except Feature 6 (Workflow Execution), which depends on Feature 1 (LLM Parameter Controls) for `user_settings.temperature`/`max_tokens`. Implement in order 1→2→3→4→5→6. All backend changes follow the existing FastAPI + SQLAlchemy async + Alembic pattern. Frontend changes extend existing Pinia stores and Vue 3 components.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Alembic, uv, Vue 3 + TypeScript + Pinia, pypdf, python-docx (both already in `backend/pyproject.toml`)

**Spec:** `docs/superpowers/specs/2026-03-24-phase14-platform-completion-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/db/models.py` | Add `ConversationFolder`, `Notification`, `WorkflowRun` models; add `folder_id` FK to `Conversation`; add LLM param columns to `UserSettings` |
| Create | `backend/alembic/versions/<hash>_add_llm_params_to_user_settings.py` | Migration: 3 new columns on `user_settings` |
| Create | `backend/alembic/versions/<hash>_add_conversation_folders.py` | Migration: `conversation_folders` table + `folder_id` FK on `conversations` |
| Create | `backend/alembic/versions/<hash>_add_notifications.py` | Migration: `notifications` table |
| Create | `backend/alembic/versions/<hash>_add_workflow_runs.py` | Migration: `workflow_runs` table |
| Modify | `backend/app/api/settings.py` | Make `model_provider`/`model_name` optional; add 3 LLM param fields |
| Modify | `backend/app/agent/llm.py` | Change default temperature from 0 to 0.7 |
| Modify | `backend/app/agent/graph.py` | Add `temperature`/`max_tokens` params to `create_graph()` |
| Modify | `backend/app/agent/experts/code_agent.py` | Forward `temperature`/`max_tokens` |
| Modify | `backend/app/agent/experts/research_agent.py` | Forward `temperature`/`max_tokens` |
| Modify | `backend/app/agent/experts/writing_agent.py` | Forward `temperature`/`max_tokens` |
| Modify | `backend/app/api/chat.py` | Add `temperature`/`max_tokens`/`system_prompt` to `_build_expert_graph` + chat handlers; add `FileContext` to `ChatRequest` |
| Create | `backend/app/api/folders.py` | Folder CRUD API |
| Modify | `backend/app/api/conversations.py` | Add `folder_id` to `ConversationUpdate` |
| Create | `backend/app/api/chat_files.py` | `POST /api/chat/extract-file` |
| Create | `backend/app/core/pricing.py` | `PRICING` dict + `estimate_cost()` |
| Modify | `backend/app/api/usage.py` | Add `model_name` to query + cost estimation |
| Create | `backend/app/core/notifications.py` | `create_notification()` helper |
| Create | `backend/app/api/notifications.py` | Notification CRUD API |
| Modify | `backend/app/worker.py` | Wire `create_notification` in cron/webhook handlers |
| Modify | `backend/app/api/invitations.py` | Wire `create_notification` for `invitation_received` |
| Create | `backend/app/workflows/__init__.py` | Package marker |
| Create | `backend/app/workflows/executor.py` | `run_workflow()` async generator |
| Modify | `backend/app/api/workflows.py` | Add execute + runs endpoints |
| Modify | `backend/app/main.py` | Register new routers: folders, chat_files, notifications |
| Modify | `frontend/src/pages/SettingsPage.vue` | Add LLM parameter controls card |
| Modify | `frontend/src/pages/ChatPage.vue` | Add folder sidebar, file attachment support |
| Modify | `frontend/src/pages/UsagePage.vue` | Add cost column and card |
| Create | `frontend/src/stores/notification.ts` | Notification Pinia store |
| Modify | `frontend/src/stores/chat.ts` | Add folder state and actions |
| Modify | `frontend/src/pages/WorkflowStudioPage.vue` | Add run button and execution drawer |

---

## Feature 1: LLM Parameter Controls

### Task 1: Migration — Add LLM params to `user_settings`

**Files:**
- Create: `backend/alembic/versions/<hash>_add_llm_params_to_user_settings.py`

- [ ] **Step 1: Generate migration**

```bash
cd backend
uv run alembic revision --autogenerate -m "add_llm_params_to_user_settings"
```

Expected: a new file in `alembic/versions/` with a hash prefix, e.g., `a1b2c3d4e5f6_add_llm_params_to_user_settings.py`.

- [ ] **Step 2: Verify generated migration and fix if needed**

Open the generated file. The `upgrade()` should look like:

```python
def upgrade() -> None:
    op.add_column("user_settings", sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"))
    op.add_column("user_settings", sa.Column("max_tokens", sa.Integer(), nullable=True))
    op.add_column("user_settings", sa.Column("system_prompt", sa.Text(), nullable=True))
    op.create_check_constraint("ck_user_settings_temperature", "user_settings", "temperature >= 0.0 AND temperature <= 2.0")
    op.create_check_constraint("ck_user_settings_max_tokens", "user_settings", "max_tokens IS NULL OR max_tokens > 0")
```

The `downgrade()` should reverse these. If `--autogenerate` missed any columns (because the model hasn't been updated yet), you can fill them in manually after updating the model in Step 3.

- [ ] **Step 3: Add columns to `UserSettings` model in `backend/app/db/models.py`**

After line 120 (`persona_override` field), add:

```python
temperature: Mapped[float] = mapped_column(
    sa.Float, nullable=False, server_default="0.7"
)
max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
system_prompt: Mapped[str | None] = mapped_column(Text)
```

Also add `Float` to the SQLAlchemy imports at the top of `models.py` if not already present (it's imported via `from sqlalchemy import ... Float ...`). Check the existing import line and add `Float` if missing.

**Note:** `sa.Float` in the migration file and `Float` in the model — both refer to `sqlalchemy.Float`. The model file uses `from sqlalchemy import ... Float`.

- [ ] **Step 4: Run migration**

```bash
cd backend
docker compose -f ../docker-compose.yml up -d postgres
uv run alembic upgrade head
```

Expected: migration applies cleanly with no errors.

- [ ] **Step 5: Verify collect-only passes (imports work)**

```bash
uv run pytest --collect-only -q
```

Expected: all tests collected, 0 errors.

---

### Task 2: Backend — Thread temperature/max_tokens through the LLM call chain

**Files:**
- Modify: `backend/app/agent/llm.py:33-34`
- Modify: `backend/app/agent/graph.py:118-134, 152`
- Modify: `backend/app/agent/experts/code_agent.py`
- Modify: `backend/app/agent/experts/research_agent.py`
- Modify: `backend/app/agent/experts/writing_agent.py`
- Modify: `backend/app/api/settings.py:65-119`

- [ ] **Step 1: Change default temperature in `agent/llm.py`**

In `backend/app/agent/llm.py`, replace lines 33–34:
```python
    if "temperature" not in kwargs:
        kwargs["temperature"] = 0
```
With:
```python
    kwargs.setdefault("temperature", 0.7)
```

No other changes to `llm.py` needed — `get_llm()` and `get_llm_with_fallback()` already accept `**kwargs` and forward them correctly.

- [ ] **Step 2: Add `temperature` and `max_tokens` to `create_graph()` in `agent/graph.py`**

In `backend/app/agent/graph.py`, extend the `create_graph()` signature (line 118) to add two new keyword-only parameters at the end of the parameter list, before the closing `)`:

```python
def create_graph(  # noqa: C901
    provider: str,
    model: str,
    api_key: str,
    enabled_tools: list[str] | None = None,
    *,
    api_keys: list[str] | None = None,
    user_id: str | None = None,
    openai_api_key: str | None = None,
    tavily_api_key: str | None = None,
    depth: int = 0,
    mcp_tools: list[BaseTool] | None = None,
    plugin_tools: list[BaseTool] | None = None,
    conversation_id: str | None = None,
    fallback_providers: list[dict] | None = None,
    base_url: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> CompiledStateGraph:
```

Then update line 152 to pass these to `get_llm_with_fallback`:
```python
    llm = get_llm_with_fallback(
        provider, model, all_keys[0], base_url=base_url,
        temperature=temperature,
        **({"max_tokens": max_tokens} if max_tokens is not None else {}),
    )
```

- [ ] **Step 3: Add `temperature`/`max_tokens` to `create_code_agent_graph()` in `experts/code_agent.py`**

Add to function signature:
```python
def create_code_agent_graph(
    *,
    provider: str,
    model: str,
    api_key: str,
    user_id: str | None = None,
    openai_api_key: str | None = None,
    api_keys: list[str] | None = None,
    mcp_tools: list[BaseTool] | None = None,
    plugin_tools: list[BaseTool] | None = None,
    conversation_id: str | None = None,
    fallback_providers: list[dict] | None = None,
    base_url: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> CompiledStateGraph:
```

And forward them in the `create_graph()` call inside the function body:
```python
    return create_graph(
        provider,
        model,
        api_key,
        _CODE_TOOLS,
        ...existing params...,
        temperature=temperature,
        max_tokens=max_tokens,
    )
```

(Read the full function body first and add `temperature=temperature, max_tokens=max_tokens` to the existing `create_graph(...)` call.)

- [ ] **Step 4: Same change for `create_research_agent_graph()` in `experts/research_agent.py`**

Same pattern as Step 3: add `temperature: float = 0.7` and `max_tokens: int | None = None` to signature and forward to `create_graph()`.

- [ ] **Step 5: Same change for `create_writing_agent_graph()` in `experts/writing_agent.py`**

Same pattern as Steps 3–4.

- [ ] **Step 6: Extend `SettingsUpdate` and handlers in `api/settings.py`**

Replace the `SettingsUpdate` class (lines 65–70):
```python
class SettingsUpdate(BaseModel):
    model_provider: Literal["deepseek", "openai", "anthropic", "zhipuai", "ollama"] | None = None
    model_name: str | None = Field(default=None, max_length=100)
    api_keys: dict[str, str | list[str]] | None = None
    persona_override: str | None = Field(default=None, max_length=2000)
    enabled_tools: list[str] | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    system_prompt: str | None = Field(default=None, max_length=4000)
```

In the `update_settings` handler, replace the unconditional assignments at lines 99–100:
```python
    settings.model_provider = body.model_provider
    settings.model_name = body.model_name
```
With conditional assignments:
```python
    if "model_provider" in body.model_fields_set and body.model_provider:
        settings.model_provider = body.model_provider
    if "model_name" in body.model_fields_set and body.model_name:
        settings.model_name = body.model_name
```

After the `enabled_tools` block (around line 109), add:
```python
    if "temperature" in body.model_fields_set and body.temperature is not None:
        settings.temperature = body.temperature
    if "max_tokens" in body.model_fields_set:
        settings.max_tokens = body.max_tokens  # None = clear to model default
    if "system_prompt" in body.model_fields_set:
        stripped_sp = body.system_prompt.strip() if body.system_prompt else None
        settings.system_prompt = stripped_sp or None
```

In `get_settings` (line 141), add to the returned dict:
```python
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "system_prompt": settings.system_prompt,
```

Also update `DEFAULT_SETTINGS` (line 47) to include:
```python
DEFAULT_SETTINGS: dict[str, object] = {
    ...existing keys...,
    "temperature": 0.7,
    "max_tokens": None,
    "system_prompt": None,
}
```

- [ ] **Step 7: Wire temperature/max_tokens through `_build_expert_graph` in `api/chat.py`**

Read `api/chat.py` lines 248–330 to see the `_build_expert_graph` function.

Add `temperature: float = 0.7` and `max_tokens: int | None = None` to `_build_expert_graph()`'s parameter list.

Forward both to all calls inside: to `create_graph()` (the fallback path) and to each of `create_code_agent_graph()`, `create_research_agent_graph()`, `create_writing_agent_graph()`.

Then find the two call sites of `_build_expert_graph` (around lines 668 and 990). Before each call, `user_settings` is already loaded. Add `temperature=settings.temperature, max_tokens=settings.max_tokens` to each call.

- [ ] **Step 8: Wire `system_prompt` injection in `chat.py`**

Find line 507 in `chat_stream` and line 902 in `chat_regenerate`. At both sites, replace:
```python
system_msg = SystemMessage(content=build_system_prompt(llm.persona_override))
```
With:
```python
if settings.system_prompt:
    system_msg = SystemMessage(content=settings.system_prompt)
else:
    system_msg = SystemMessage(content=build_system_prompt(llm.persona_override))
```

- [ ] **Step 9: Run collect-only to verify no import errors**

```bash
cd backend
uv run pytest --collect-only -q
```

Expected: 0 errors.

- [ ] **Step 10: Commit**

```bash
git add backend/app/db/models.py \
        backend/app/agent/llm.py \
        backend/app/agent/graph.py \
        backend/app/agent/experts/code_agent.py \
        backend/app/agent/experts/research_agent.py \
        backend/app/agent/experts/writing_agent.py \
        backend/app/api/settings.py \
        backend/app/api/chat.py \
        backend/alembic/versions/*add_llm_params*
git commit -m "feat: add LLM parameter controls (temperature, max_tokens, system_prompt)"
```

---

### Task 3: Frontend — LLM parameter controls in SettingsPage

**Files:**
- Modify: `frontend/src/pages/SettingsPage.vue`

- [ ] **Step 1: Extend settings store/API to load and save new fields**

In `SettingsPage.vue`, find where settings are loaded (the `GET /api/settings` call) and where they are saved (the `PUT /api/settings` call). Add three reactive refs:

```typescript
const temperature = ref<number>(0.7)
const maxTokens = ref<number | null>(null)
const systemPrompt = ref<string>('')
```

Populate them from the loaded settings response:
```typescript
temperature.value = data.temperature ?? 0.7
maxTokens.value = data.max_tokens ?? null
systemPrompt.value = data.system_prompt ?? ''
```

- [ ] **Step 2: Add save handlers for the three fields**

Each field auto-saves on blur. Create a reusable save function or three individual ones that call `PUT /api/settings` with only the relevant field in the body:

```typescript
async function saveTemperature() {
  await api.put('/settings', { temperature: temperature.value })
}
async function saveMaxTokens() {
  await api.put('/settings', { max_tokens: maxTokens.value })
}
async function saveSystemPrompt() {
  const val = systemPrompt.value.trim() || null
  await api.put('/settings', { system_prompt: val })
}
```

- [ ] **Step 3: Add "Model Parameters" card to template**

After the existing model selector card, add:

```html
<div class="settings-card">
  <h3>{{ $t('settings.modelParams') }}</h3>

  <!-- Temperature -->
  <div class="param-row">
    <label>{{ $t('settings.temperature') }}</label>
    <input type="range" min="0" max="2" step="0.1"
           v-model.number="temperature"
           @change="saveTemperature" />
    <span>{{ temperature.toFixed(1) }}</span>
  </div>

  <!-- Max Tokens -->
  <div class="param-row">
    <label>{{ $t('settings.maxTokens') }}</label>
    <input type="number" min="256" max="32768" placeholder="Model default"
           :value="maxTokens ?? ''"
           @change="e => { maxTokens = e.target.value ? Number(e.target.value) : null; saveMaxTokens() }" />
  </div>

  <!-- System Prompt -->
  <div class="param-row param-row--column">
    <label>{{ $t('settings.systemPrompt') }}</label>
    <textarea rows="4"
              v-model="systemPrompt"
              @blur="saveSystemPrompt"
              :placeholder="$t('settings.systemPromptPlaceholder')" />
  </div>
</div>
```

- [ ] **Step 4: Add i18n keys**

In `frontend/src/locales/zh.ts` (and `en.ts`), add under the `settings` section:
```typescript
modelParams: '模型参数',
temperature: '温度',
maxTokens: '最大 Token 数',
systemPrompt: '系统提示词',
systemPromptPlaceholder: '覆盖助手的默认行为...',
```

- [ ] **Step 5: Verify frontend type-check passes**

```bash
cd frontend
bun run type-check
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SettingsPage.vue frontend/src/locales/
git commit -m "feat: add model parameter controls to settings page"
```

---

## Feature 2: Conversation Folders

### Task 4: Migration + Models for Conversation Folders

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/<hash>_add_conversation_folders.py`

- [ ] **Step 1: Add `ConversationFolder` model to `db/models.py`**

After the `ConversationTag` class (around line 207), add:

```python
class ConversationFolder(Base):
    __tablename__ = "conversation_folders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="folder", passive_deletes=True
    )
```

- [ ] **Step 2: Add `folder_id` FK to `Conversation` model**

In the `Conversation` class, after `workspace_id` (around line 165), add:

```python
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
```

Also add the relationship on `Conversation`:
```python
    folder: Mapped["ConversationFolder | None"] = relationship(
        "ConversationFolder", back_populates="conversations"
    )
```

- [ ] **Step 3: Generate and verify migration**

```bash
cd backend
uv run alembic revision --autogenerate -m "add_conversation_folders"
```

Open the generated file and verify `upgrade()` creates `conversation_folders` table and adds `folder_id` column to `conversations`. Fix any issues with ordering (table must be created before FK is added).

- [ ] **Step 4: Run migration**

```bash
uv run alembic upgrade head
```

- [ ] **Step 5: Run collect-only**

```bash
uv run pytest --collect-only -q
```

---

### Task 5: Backend — Folder CRUD API

**Files:**
- Create: `backend/app/api/folders.py`
- Modify: `backend/app/api/conversations.py:49-58, 537-541`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create `backend/app/api/folders.py`**

```python
"""Conversation folder CRUD."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import ConversationFolder, User
from app.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/folders", tags=["folders"])


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str | None = Field(default=None, max_length=7)


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = None
    display_order: int | None = None


class FolderOut(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None = None
    display_order: int
    model_config = {"from_attributes": True}


@router.get("", response_model=list[FolderOut])
async def list_folders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationFolder]:
    result = await db.execute(
        select(ConversationFolder)
        .where(ConversationFolder.user_id == user.id)
        .order_by(ConversationFolder.display_order, ConversationFolder.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=FolderOut, status_code=201)
async def create_folder(
    body: FolderCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationFolder:
    folder = ConversationFolder(
        user_id=user.id,
        name=body.name.strip(),
        color=body.color,
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    logger.info("folder_created", user_id=str(user.id), folder_id=str(folder.id))
    return folder


@router.patch("/{folder_id}", response_model=FolderOut)
async def update_folder(
    folder_id: uuid.UUID,
    body: FolderUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationFolder:
    folder = await db.scalar(
        select(ConversationFolder).where(
            ConversationFolder.id == folder_id,
            ConversationFolder.user_id == user.id,
        )
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    if "name" in body.model_fields_set and body.name:
        folder.name = body.name.strip()
    if "color" in body.model_fields_set:
        folder.color = body.color
    if "display_order" in body.model_fields_set and body.display_order is not None:
        folder.display_order = body.display_order
    await db.commit()
    await db.refresh(folder)
    return folder


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    folder = await db.scalar(
        select(ConversationFolder).where(
            ConversationFolder.id == folder_id,
            ConversationFolder.user_id == user.id,
        )
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    await db.delete(folder)
    await db.commit()
```

- [ ] **Step 2: Add `folder_id` to `ConversationUpdate` in `api/conversations.py`**

In `ConversationUpdate` (lines 49–58), add:
```python
    folder_id: uuid.UUID | None = None
```

Import `uuid` at the top if not already imported (it is — check existing imports).

In the `update_conversation` handler (lines 537–541), add after the `persona_override` check:
```python
    if "folder_id" in body.model_fields_set:
        conv.folder_id = body.folder_id
```

- [ ] **Step 3: Register `folders_router` in `main.py`**

Add import at the top of `main.py` (after the existing router imports):
```python
from app.api.folders import router as folders_router
```

Add after `app.include_router(conversations_router)`:
```python
app.include_router(folders_router)
```

- [ ] **Step 4: Run collect-only**

```bash
cd backend
uv run pytest --collect-only -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models.py \
        backend/app/api/folders.py \
        backend/app/api/conversations.py \
        backend/app/main.py \
        backend/alembic/versions/*add_conversation_folders*
git commit -m "feat: add conversation folders"
```

---

### Task 6: Frontend — Folder sidebar and conversation assignment

**Files:**
- Modify: `frontend/src/stores/chat.ts`
- Modify: `frontend/src/pages/ChatPage.vue`

- [ ] **Step 1: Add folder state and actions to `chat.ts` Pinia store**

In `frontend/src/stores/chat.ts`, add a `Folder` interface and extend the store:

```typescript
export interface Folder {
  id: string
  name: string
  color: string | null
  display_order: number
}
```

Add to store state:
```typescript
folders: [] as Folder[],
activeFolderFilter: null as string | null,
```

Add store actions:
```typescript
async fetchFolders() {
  const { data } = await api.get<Folder[]>('/folders')
  this.folders = data
},
async createFolder(name: string, color?: string) {
  const { data } = await api.post<Folder>('/folders', { name, color })
  this.folders.push(data)
  return data
},
async updateFolder(id: string, patch: Partial<Folder>) {
  const { data } = await api.patch<Folder>(`/folders/${id}`, patch)
  const idx = this.folders.findIndex(f => f.id === id)
  if (idx >= 0) this.folders[idx] = data
},
async deleteFolder(id: string) {
  await api.delete(`/folders/${id}`)
  this.folders = this.folders.filter(f => f.id !== id)
  if (this.activeFolderFilter === id) this.activeFolderFilter = null
},
async moveConversationToFolder(convId: string, folderId: string | null) {
  await api.patch(`/conversations/${convId}`, { folder_id: folderId })
  const conv = this.conversations.find(c => c.id === convId)
  if (conv) (conv as any).folder_id = folderId
},
```

Update the `filteredConversations` computed (or equivalent filtering logic) to filter by `activeFolderFilter` when set.

- [ ] **Step 2: Add folder sidebar section to `ChatPage.vue`**

In the sidebar section, above the conversation list, add a folder filter section:

```html
<!-- Folder filter -->
<div class="folder-list">
  <div
    class="folder-item"
    :class="{ active: chatStore.activeFolderFilter === null }"
    @click="chatStore.activeFolderFilter = null"
  >
    {{ $t('chat.allConversations') }}
  </div>
  <div
    v-for="folder in chatStore.folders"
    :key="folder.id"
    class="folder-item"
    :class="{ active: chatStore.activeFolderFilter === folder.id }"
    @click="chatStore.activeFolderFilter = folder.id"
    @contextmenu.prevent="showFolderMenu($event, folder)"
  >
    <span class="folder-dot" :style="{ background: folder.color || '#94a3b8' }" />
    {{ folder.name }}
  </div>
  <button class="folder-add-btn" @click="promptCreateFolder">+</button>
</div>
```

- [ ] **Step 3: Add "Move to folder" to conversation context menu**

In the existing right-click context menu for conversations, add a "Move to folder" submenu:

```html
<div class="ctx-menu-item" @click="showMoveFolderMenu = convId">
  {{ $t('chat.moveToFolder') }}
  <div v-if="showMoveFolderMenu === convId" class="submenu">
    <div @click="chatStore.moveConversationToFolder(convId, null)">
      {{ $t('chat.noFolder') }}
    </div>
    <div
      v-for="folder in chatStore.folders"
      :key="folder.id"
      @click="chatStore.moveConversationToFolder(convId, folder.id)"
    >
      {{ folder.name }}
    </div>
  </div>
</div>
```

- [ ] **Step 4: Call `fetchFolders` on mount**

In the `onMounted` hook (or `setup`), add:
```typescript
await chatStore.fetchFolders()
```

- [ ] **Step 5: Add i18n keys**

```typescript
allConversations: '所有对话',
moveToFolder: '移动到文件夹',
noFolder: '无文件夹',
newFolder: '新建文件夹',
```

- [ ] **Step 6: Type-check**

```bash
cd frontend && bun run type-check
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/chat.ts frontend/src/pages/ChatPage.vue frontend/src/locales/
git commit -m "feat: add folder sidebar and conversation folder assignment"
```

---

## Feature 3: File Attachments in Chat

### Task 7: Backend — File extraction endpoint

**Files:**
- Create: `backend/app/api/chat_files.py`
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create `backend/app/api/chat_files.py`**

```python
"""Stateless file text extraction for chat file attachments."""

from __future__ import annotations

import io

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.db.models import User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_TEXT_CHARS = 30_000

_ALLOWED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "text/markdown",
}


class ExtractFileResponse(BaseModel):
    filename: str
    char_count: int
    extracted_text: str


@router.post("/extract-file", response_model=ExtractFileResponse)
@limiter.limit("10/minute")
async def extract_file(
    request: Request,
    file: UploadFile,
    _user: User = Depends(get_current_user),
) -> ExtractFileResponse:
    """Extract text from an uploaded file (PDF, DOCX, TXT, CSV, MD)."""
    content_type = file.content_type or ""
    # Normalise text/* subtypes
    if content_type.startswith("text/"):
        content_type = content_type.split(";")[0].strip()

    if content_type not in _ALLOWED_MIMES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {content_type}. Allowed: PDF, DOCX, TXT, CSV, MD",
        )

    raw = await file.read()
    if len(raw) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    try:
        text = _extract(content_type, raw)
    except Exception as exc:
        logger.warning("file_extraction_failed", filename=file.filename, exc_info=True)
        raise HTTPException(status_code=422, detail=f"Extraction failed: {exc}") from exc

    truncated = text[:_MAX_TEXT_CHARS]
    return ExtractFileResponse(
        filename=file.filename or "attachment",
        char_count=len(truncated),
        extracted_text=truncated,
    )


def _extract(content_type: str, raw: bytes) -> str:
    if content_type == "application/pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from docx import Document

        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)

    # TXT / CSV / MD
    return raw.decode("utf-8", errors="replace")
```

- [ ] **Step 2: Add `FileContext` to `ChatRequest` in `api/chat.py`**

Near the top of `api/chat.py` where `ChatRequest` is defined, add the `FileContext` model before `ChatRequest` and extend `ChatRequest`:

```python
class FileContext(BaseModel):
    filename: str = Field(max_length=255)
    extracted_text: str = Field(max_length=30_000)
```

In `ChatRequest`, add:
```python
    file_context: FileContext | None = None
```

- [ ] **Step 3: Prepend file content in `chat_stream`**

In the `chat_stream` handler in `api/chat.py`, find where `content` is assembled for the human message (the `Message(role="human", content=...)` creation before the DB insert). Add:

```python
if body.file_context:
    content = (
        f"[Attached file: {body.file_context.filename}]\n"
        f"{body.file_context.extracted_text}\n\n---\n{content}"
    )
```

- [ ] **Step 4: Register `chat_files_router` in `main.py`**

```python
from app.api.chat_files import router as chat_files_router
```

Add after `app.include_router(chat_router)`:
```python
app.include_router(chat_files_router)
```

- [ ] **Step 5: Run collect-only**

```bash
cd backend && uv run pytest --collect-only -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/chat_files.py backend/app/api/chat.py backend/app/main.py
git commit -m "feat: add file attachment extraction endpoint for chat"
```

---

### Task 8: Frontend — File attachment UI in ChatPage

**Files:**
- Modify: `frontend/src/pages/ChatPage.vue`

- [ ] **Step 1: Extend file input to accept documents**

Find the paperclip `<input>` element in `ChatPage.vue` that currently has `accept="image/*"`. Change to:
```html
<input type="file" accept="image/*,.pdf,.docx,.txt,.csv,.md" @change="handleFileSelect" />
```

- [ ] **Step 2: Add document extraction state**

```typescript
const attachedFile = ref<{ filename: string; char_count: number; extracted_text: string } | null>(null)
const fileUploading = ref(false)
```

- [ ] **Step 3: Route file selection**

In `handleFileSelect`, add document routing logic:

```typescript
async function handleFileSelect(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return

  if (file.type.startsWith('image/')) {
    // existing base64 flow — unchanged
    handleImageFile(file)
    return
  }

  // Document extraction
  fileUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/chat/extract-file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    attachedFile.value = data
  } catch (err) {
    toast.error(t('chat.fileExtractionFailed'))
  } finally {
    fileUploading.value = false
  }
}
```

- [ ] **Step 4: Show file chip in input area**

```html
<div v-if="fileUploading" class="file-chip file-chip--loading">
  <span class="spinner" /> {{ $t('chat.extracting') }}
</div>
<div v-else-if="attachedFile" class="file-chip">
  {{ attachedFile.filename }} ({{ attachedFile.char_count }} chars)
  <button @click="attachedFile = null">×</button>
</div>
```

- [ ] **Step 5: Include `file_context` in send payload**

In the send function, extend the request body:
```typescript
const payload = {
  ...,
  file_context: attachedFile.value ?? undefined,
}
```

Clear `attachedFile` after sending.

- [ ] **Step 6: Add i18n keys**

```typescript
extracting: '提取中...',
fileExtractionFailed: '文件提取失败，请重试',
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ChatPage.vue frontend/src/locales/
git commit -m "feat: add document file attachment support to chat"
```

---

## Feature 4: Cost Estimation

### Task 9: Backend + Frontend — Cost estimation

**Files:**
- Create: `backend/app/core/pricing.py`
- Modify: `backend/app/api/usage.py`
- Modify: `frontend/src/pages/UsagePage.vue`

- [ ] **Step 1: Create `backend/app/core/pricing.py`**

```python
"""Static LLM pricing table for cost estimation.

Prices are USD per 1 million tokens: (input_price, output_price).
Update this dict as provider pricing changes.
"""

PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "deepseek": {
        "deepseek-chat": (0.27, 1.10),
        "deepseek-reasoner": (0.55, 2.19),
    },
    "openai": {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4-turbo": (10.00, 30.00),
        "o1": (15.00, 60.00),
        "o1-mini": (1.10, 4.40),
    },
    "anthropic": {
        "claude-opus-4-5": (15.00, 75.00),
        "claude-sonnet-4-6": (3.00, 15.00),
        "claude-haiku-4-5-20251001": (0.80, 4.00),
        "claude-3-5-haiku-20241022": (0.80, 4.00),
        "claude-3-5-sonnet-20241022": (3.00, 15.00),
    },
    "zhipuai": {
        "glm-4": (0.10, 0.10),
        "glm-4-flash": (0.00, 0.00),
        "glm-4-plus": (0.14, 0.14),
        "glm-4.5": (0.14, 0.14),
    },
    "ollama": {},  # local inference = free
}


def estimate_cost(provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
    """Return estimated USD cost. Returns 0.0 for unknown provider/model."""
    prices = PRICING.get(provider, {}).get(model)
    if not prices:
        return 0.0
    in_price, out_price = prices
    return (tokens_in * in_price + tokens_out * out_price) / 1_000_000
```

- [ ] **Step 2: Update `api/usage.py` to add `model_name` and cost**

Replace the query in `get_usage_summary`:

```python
    stmt = select(
        func.date(Message.created_at).label("day"),
        Message.model_provider,
        Message.model_name,
        func.coalesce(func.sum(Message.tokens_input), 0).label("tokens_in"),
        func.coalesce(func.sum(Message.tokens_output), 0).label("tokens_out"),
        func.count().label("message_count"),
    ).join(Conversation, Message.conversation_id == Conversation.id)
```

Update the GROUP BY:
```python
    ).group_by(func.date(Message.created_at), Message.model_provider, Message.model_name)
```

Import `estimate_cost` at the top:
```python
from app.core.pricing import estimate_cost
```

Update the daily row construction:
```python
    daily = [
        {
            "day": str(r.day),
            "provider": r.model_provider or "unknown",
            "model": r.model_name or "unknown",
            "tokens_in": int(r.tokens_in),
            "tokens_out": int(r.tokens_out),
            "messages": int(r.message_count),
            "estimated_cost_usd": estimate_cost(
                r.model_provider or "", r.model_name or "",
                int(r.tokens_in), int(r.tokens_out)
            ),
        }
        for r in rows.all()
    ]
```

Update the return dict to add:
```python
        "total_estimated_cost_usd": sum(d["estimated_cost_usd"] for d in daily),
```

- [ ] **Step 3: Run collect-only**

```bash
cd backend && uv run pytest --collect-only -q
```

- [ ] **Step 4: Update `UsagePage.vue` to show cost**

Find the summary cards section and add a cost card:
```html
<div class="stat-card">
  <div class="stat-value">${{ formatCost(usageData.total_estimated_cost_usd) }}</div>
  <div class="stat-label">{{ $t('usage.estimatedCost') }}</div>
</div>
```

Add a cost column to the daily usage table:
```html
<td>${{ formatCost(row.estimated_cost_usd) }}</td>
```

Add the `formatCost` helper:
```typescript
function formatCost(usd: number): string {
  if (usd < 0.0001) return '< $0.0001'
  return `$${usd.toPrecision(4)}`
}
```

Add disclaimer below the table:
```html
<p class="disclaimer">{{ $t('usage.costDisclaimer') }}</p>
```

Add i18n keys:
```typescript
estimatedCost: '预估费用',
costDisclaimer: '费用基于公开定价估算，实际费用可能不同。',
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/pricing.py backend/app/api/usage.py \
        frontend/src/pages/UsagePage.vue frontend/src/locales/
git commit -m "feat: add cost estimation to usage page"
```

---

## Feature 5: In-App Notification System

### Task 10: Migration + Models + Helper for Notifications

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/<hash>_add_notifications.py`
- Create: `backend/app/core/notifications.py`

- [ ] **Step 1: Add `Notification` model to `db/models.py`**

After the `AuditLog` model (find it in the file), add:

```python
class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "type IN ('cron_completed','cron_failed','webhook_failed',"
            "'invitation_received','workflow_completed','workflow_failed')",
            name="ck_notifications_type",
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
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    action_url: Mapped[str | None] = mapped_column(String(200))
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
```

- [ ] **Step 2: Generate and apply migration**

```bash
cd backend
uv run alembic revision --autogenerate -m "add_notifications"
# verify the generated file, then:
uv run alembic upgrade head
```

- [ ] **Step 3: Create `backend/app/core/notifications.py`**

```python
"""In-app notification creation helper.

Same call-and-forget pattern as log_action() in app/core/audit.py.
Safe to call from worker.py and API handlers.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.db.models import Notification
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)


async def create_notification(
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str,
    *,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist a notification. Failures are swallowed."""
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                session.add(
                    Notification(
                        user_id=user_id,
                        type=type,
                        title=title,
                        body=body,
                        action_url=action_url,
                        metadata_json=metadata or {},
                    )
                )
    except Exception:
        logger.warning(
            "create_notification_failed",
            user_id=str(user_id),
            type=type,
            exc_info=True,
        )
```

- [ ] **Step 4: Run collect-only**

```bash
cd backend && uv run pytest --collect-only -q
```

---

### Task 11: Backend — Notification API and wiring

**Files:**
- Create: `backend/app/api/notifications.py`
- Modify: `backend/app/worker.py`
- Modify: `backend/app/api/invitations.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create `backend/app/api/notifications.py`**

```python
"""Notification API — list, mark as read, delete."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import Notification, User
from app.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    is_read: bool
    action_url: str | None = None
    created_at: str
    model_config = {"from_attributes": True}

    def model_post_init(self, __context: object) -> None:
        if hasattr(self, "created_at") and not isinstance(self.created_at, str):
            object.__setattr__(self, "created_at", self.created_at.isoformat())


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/unread-count")
async def get_unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy import func as sqlfunc

    count = await db.scalar(
        select(sqlfunc.count()).where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
    )
    return {"count": count or 0}


@router.patch("/{notification_id}/read", status_code=204)
async def mark_notification_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user.id)
        .values(is_read=True)
    )
    await db.commit()


@router.post("/read-all", status_code=204)
async def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id)
        .values(is_read=True)
    )
    await db.commit()


@router.delete("/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    notif = await db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.delete(notif)
    await db.commit()
```

- [ ] **Step 2: Wire notifications in `worker.py` — cron job events**

In `backend/app/worker.py`, add import:
```python
from app.core.notifications import create_notification
```

Find the `execute_cron_job` function. After a successful job run, add:
```python
await create_notification(
    job.user_id,
    "cron_completed",
    f"Cron job completed: {job.name}",
    "Your scheduled task finished successfully.",
    action_url="/cron",
)
```

In the exception handler for job failures, add:
```python
await create_notification(
    job.user_id,
    "cron_failed",
    f"Cron job failed: {job.name}",
    f"Error: {str(exc)[:200]}",
    action_url="/cron",
)
```

(Read the `execute_cron_job` function first to find the exact success/failure points.)

- [ ] **Step 3: Wire `webhook_failed` notification in `worker.py`**

In `deliver_webhook`, after the retry block (after line 193's `raise` statement, in the else path where `final_status == "failed"` and no retry), add before `logger.info("deliver_webhook_done", ...)`:

```python
if final_status == "failed":
    # Look up the webhook's user_id from the delivery record
    # (already loaded above as `webhook` or `delivery` — check function context)
    await create_notification(
        webhook.user_id,
        "webhook_failed",
        "Webhook delivery failed",
        f"All retry attempts exhausted for webhook '{webhook.name}'.",
        action_url="/settings",
    )
```

Read `deliver_webhook` (lines ~100–200) to find the exact variable names for the webhook object and its `user_id`.

- [ ] **Step 4: Wire `invitation_received` in `api/invitations.py`**

In `invite_member` (starting line 44), after the invitation is created and committed, check if the invited email belongs to an existing user and create a notification:

```python
from app.core.notifications import create_notification

# After invitation commit, check if invited email is an existing user
invited_user = await db.scalar(select(User).where(User.email == body.email))
if invited_user:
    await create_notification(
        invited_user.id,
        "invitation_received",
        f"Invitation to workspace: {ws.name}",
        f"{user.display_name or user.email} invited you to join {ws.name}.",
        action_url=f"/invite/{inv.token}",
    )
```

- [ ] **Step 5: Register `notifications_router` in `main.py`**

```python
from app.api.notifications import router as notifications_router
```

Add:
```python
app.include_router(notifications_router)
```

- [ ] **Step 6: Run collect-only**

```bash
cd backend && uv run pytest --collect-only -q
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/db/models.py \
        backend/app/core/notifications.py \
        backend/app/api/notifications.py \
        backend/app/worker.py \
        backend/app/api/invitations.py \
        backend/app/main.py \
        backend/alembic/versions/*add_notifications*
git commit -m "feat: add in-app notification system"
```

---

### Task 12: Frontend — Notification bell and polling

**Files:**
- Create: `frontend/src/stores/notification.ts`
- Modify: `frontend/src/App.vue` (or the main layout component — find where the header is)

- [ ] **Step 1: Create `frontend/src/stores/notification.ts`**

```typescript
import { defineStore } from 'pinia'
import api from '@/api'

export interface Notification {
  id: string
  type: string
  title: string
  body: string
  is_read: boolean
  action_url: string | null
  created_at: string
}

export const useNotificationStore = defineStore('notification', {
  state: () => ({
    notifications: [] as Notification[],
    unreadCount: 0,
  }),
  actions: {
    async fetchUnreadCount() {
      const { data } = await api.get<{ count: number }>('/notifications/unread-count')
      this.unreadCount = data.count
    },
    async fetchNotifications() {
      const { data } = await api.get<Notification[]>('/notifications?limit=10')
      this.notifications = data
    },
    async markRead(id: string) {
      await api.patch(`/notifications/${id}/read`)
      const n = this.notifications.find(n => n.id === id)
      if (n) n.is_read = true
      this.unreadCount = Math.max(0, this.unreadCount - 1)
    },
    async markAllRead() {
      await api.post('/notifications/read-all')
      this.notifications.forEach(n => { n.is_read = true })
      this.unreadCount = 0
    },
  },
})
```

- [ ] **Step 2: Add bell icon to header**

Find the main header component (likely in `App.vue` or a layout component). Add:

```html
<div class="notification-bell" @click="toggleNotificationPanel">
  <span class="bell-icon">🔔</span>
  <span v-if="notificationStore.unreadCount > 0" class="bell-badge">
    {{ notificationStore.unreadCount }}
  </span>

  <!-- Dropdown panel -->
  <div v-if="showNotificationPanel" class="notification-panel">
    <div class="notification-header">
      <span>{{ $t('notifications.title') }}</span>
      <button @click.stop="notificationStore.markAllRead()">
        {{ $t('notifications.markAllRead') }}
      </button>
    </div>
    <div
      v-for="n in notificationStore.notifications"
      :key="n.id"
      class="notification-item"
      :class="{ unread: !n.is_read }"
      @click="handleNotificationClick(n)"
    >
      <div class="notification-title">{{ n.title }}</div>
      <div class="notification-body">{{ n.body }}</div>
    </div>
    <div v-if="notificationStore.notifications.length === 0" class="notification-empty">
      {{ $t('notifications.empty') }}
    </div>
  </div>
</div>
```

- [ ] **Step 3: Set up polling**

In the header component's `setup()` or `onMounted`:

```typescript
const notificationStore = useNotificationStore()
let pollInterval: ReturnType<typeof setInterval>

onMounted(async () => {
  await notificationStore.fetchUnreadCount()
  pollInterval = setInterval(() => notificationStore.fetchUnreadCount(), 30_000)

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) notificationStore.fetchUnreadCount()
  })
})

onUnmounted(() => {
  clearInterval(pollInterval)
})

function handleNotificationClick(n: Notification) {
  notificationStore.markRead(n.id)
  if (n.action_url) router.push(n.action_url)
  showNotificationPanel.value = false
}
```

- [ ] **Step 4: Add i18n keys**

```typescript
notifications: {
  title: '通知',
  markAllRead: '全部已读',
  empty: '暂无通知',
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/notification.ts frontend/src/App.vue frontend/src/locales/
git commit -m "feat: add notification bell with 30-second polling"
```

---

## Feature 6: Workflow Execution Engine

> **Prerequisite:** Feature 1 (LLM Parameter Controls) must be completed and migrated before this task — the executor reads `user_settings.temperature` and `user_settings.max_tokens`.

### Task 13: Migration + Model for WorkflowRun

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/<hash>_add_workflow_runs.py`

- [ ] **Step 1: Add `WorkflowRun` model to `db/models.py`**

After the `Workflow` model (find it in the file), add:

```python
class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','completed','failed')",
            name="ck_workflow_runs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    input_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    output_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    run_log: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workflow: Mapped["Workflow"] = relationship("Workflow")
```

- [ ] **Step 2: Generate and apply migration**

```bash
cd backend
uv run alembic revision --autogenerate -m "add_workflow_runs"
uv run alembic upgrade head
```

- [ ] **Step 3: Run collect-only**

```bash
uv run pytest --collect-only -q
```

---

### Task 14: Backend — Workflow executor

**Files:**
- Create: `backend/app/workflows/__init__.py`
- Create: `backend/app/workflows/executor.py`

- [ ] **Step 1: Create `backend/app/workflows/__init__.py`**

Empty file (package marker):
```python
```

- [ ] **Step 2: Create `backend/app/workflows/executor.py`**

```python
"""Workflow execution engine.

Executes the JARVIS workflow DSL (nodes + edges) as an async generator
that yields per-node progress events.

DSL schema: { "nodes": [...], "edges": [...] }
Node types: input, output, llm, tool, condition
Variable interpolation: {{variable_name}} or {{node_id.output}}
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import structlog

from app.db.models import UserSettings, Workflow, WorkflowRun
from app.db.session import AsyncSessionLocal

# _TOOL_MAP is a module-private dict in app.agent.graph; cross-module import
# is intentional here — the workflow executor needs the same tool instances.
from app.agent.graph import _TOOL_MAP  # noqa: PLC2701

logger = structlog.get_logger(__name__)

_MAX_NODES = 50
_MAX_WALL_SECONDS = 300  # 5 minutes


def _interpolate(template: str, context: dict) -> str:
    """Replace {{key}} and {{node_id.output}} placeholders with context values."""
    def _replace(m: re.Match) -> str:
        key = m.group(1)
        parts = key.split(".", 1)
        if len(parts) == 1:
            val = context.get(parts[0])
        else:
            nested = context.get(parts[0])
            val = nested.get(parts[1], "") if isinstance(nested, dict) else ""
        return str(val) if val is not None else ""

    return re.sub(r"\{\{([\w.]+)\}\}", _replace, template)


def _topo_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Kahn's topological sort. Raises ValueError on cycle."""
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    adj: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        adj[edge["source"]].append(edge["target"])
        in_degree[edge["target"]] = in_degree.get(edge["target"], 0) + 1

    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    order: list[str] = []
    while queue:
        nid = queue.popleft()
        order.append(nid)
        for neighbor in adj[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(nodes):
        raise ValueError("Workflow contains a cycle")
    return order


def _eval_condition(left: str, operator: str, right: str) -> bool:
    """Evaluate a condition with explicit operator dispatch. No dynamic eval."""
    match operator:
        case "equals":
            return left == right
        case "contains":
            return right in left
        case "startswith":
            return left.startswith(right)
        case "endswith":
            return left.endswith(right)
        case "gt":
            try:
                return float(left) > float(right)
            except ValueError:
                return False
        case "lt":
            try:
                return float(left) < float(right)
            except ValueError:
                return False
        case _:
            logger.warning("unknown_condition_operator", operator=operator)
            return True  # non-blocking default


async def run_workflow(
    workflow: Workflow,
    input_data: dict,
    user_settings: UserSettings,
) -> AsyncGenerator[dict, None]:
    """Execute a workflow DSL and yield progress events.

    Yields:
        { "type": "node_done", "node_id": str, "output": str, "duration_ms": int }
        { "type": "run_done", "run_id": str, "status": "completed"|"failed" }
    """
    dsl: dict = workflow.dsl or {}
    nodes: list[dict] = dsl.get("nodes", [])
    edges: list[dict] = dsl.get("edges", [])

    if len(nodes) > _MAX_NODES:
        raise ValueError(f"Workflow exceeds maximum node count ({_MAX_NODES})")

    # Create WorkflowRun record
    run_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        async with db.begin():
            run = WorkflowRun(
                id=run_id,
                workflow_id=workflow.id,
                user_id=workflow.user_id,
                status="running",
                input_data=input_data,
            )
            db.add(run)

    node_map = {n["id"]: n for n in nodes}
    context: dict[str, Any] = {}
    run_log: list[dict] = []
    final_status = "completed"
    error_message: str | None = None

    try:
        order = _topo_sort(nodes, edges)
        async with asyncio.timeout(_MAX_WALL_SECONDS):
            for node_id in order:
                node = node_map[node_id]
                node_type = node["type"]
                data = node.get("data", {})
                t0 = time.monotonic()
                output = ""

                try:
                    if node_type == "input":
                        var = data.get("variable", node_id)
                        output = str(input_data.get(var, ""))
                        context[var] = output

                    elif node_type == "output":
                        output = _interpolate(data.get("value", ""), context)

                    elif node_type == "llm":
                        from app.agent.llm import get_llm_with_fallback

                        api_keys_raw = user_settings.api_keys or {}
                        # Decrypt keys if encrypted (same as chat.py pattern)
                        from app.core.security import decrypt_api_keys
                        raw_keys = decrypt_api_keys(api_keys_raw)
                        provider_key = raw_keys.get(user_settings.model_provider)
                        if isinstance(provider_key, list):
                            provider_key = provider_key[0] if provider_key else ""
                        provider_key = provider_key or ""

                        llm = get_llm_with_fallback(
                            user_settings.model_provider,
                            user_settings.model_name,
                            provider_key,
                            temperature=user_settings.temperature,
                            **({"max_tokens": user_settings.max_tokens}
                               if user_settings.max_tokens else {}),
                        )
                        prompt = _interpolate(data.get("prompt", ""), context)
                        from langchain_core.messages import HumanMessage
                        response = await llm.ainvoke([HumanMessage(content=prompt)])
                        output = response.content if hasattr(response, "content") else str(response)

                    elif node_type == "tool":
                        tool_name = data.get("tool_name", "")
                        tool = _TOOL_MAP.get(tool_name)
                        if not tool:
                            raise ValueError(f"Unknown tool: {tool_name}")
                        params = {
                            k: _interpolate(str(v), context)
                            for k, v in data.get("params", {}).items()
                        }
                        result = await tool.arun(params) if hasattr(tool, "arun") else tool.run(params)
                        output = str(result)

                    elif node_type == "condition":
                        left = _interpolate(data.get("left", ""), context)
                        right = _interpolate(data.get("right", ""), context)
                        operator = data.get("operator", "equals")
                        result = _eval_condition(left, operator, right)
                        output = str(result)

                except Exception as exc:
                    output = f"[Error in node {node_id}: {exc}]"
                    logger.warning("workflow_node_error", node_id=node_id, exc_info=True)

                duration_ms = int((time.monotonic() - t0) * 1000)
                context[node_id] = {"output": output}
                run_log.append({
                    "node_id": node_id,
                    "status": "done",
                    "output": output[:500],
                    "duration_ms": duration_ms,
                    "timestamp": datetime.now(UTC).isoformat(),
                })

                yield {
                    "type": "node_done",
                    "node_id": node_id,
                    "output": output,
                    "duration_ms": duration_ms,
                }

    except asyncio.TimeoutError:
        final_status = "failed"
        error_message = "Workflow exceeded 5-minute time limit"
    except asyncio.CancelledError:
        # Client disconnected — mark as failed, then re-raise so FastAPI
        # can clean up the streaming response correctly.
        final_status = "failed"
        error_message = "Cancelled"
        raise
    except ValueError as exc:
        final_status = "failed"
        error_message = str(exc)
    except Exception as exc:
        final_status = "failed"
        error_message = f"Unexpected error: {exc}"
        logger.exception("workflow_execution_error", workflow_id=str(workflow.id))

    # Persist final run state
    output_data = {nid: ctx for nid, ctx in context.items() if isinstance(ctx, dict)}
    async with AsyncSessionLocal() as db:
        async with db.begin():
            run_obj = await db.get(WorkflowRun, run_id)
            if run_obj:
                run_obj.status = final_status
                run_obj.output_data = output_data
                run_obj.error_message = error_message
                run_obj.run_log = run_log
                run_obj.completed_at = datetime.now(UTC)

    yield {"type": "run_done", "run_id": str(run_id), "status": final_status}
```

- [ ] **Step 3: Run collect-only**

```bash
cd backend && uv run pytest --collect-only -q
```

Expected: 0 import errors. If `_TOOL_MAP` import fails, read `app/agent/graph.py` to find the actual name and correct it.

- [ ] **Step 4: Commit executor**

```bash
git add backend/app/workflows/
git commit -m "feat: add workflow executor with Kahn topological sort and SSE streaming"
```

---

### Task 15: Backend — Workflow API extensions

**Files:**
- Modify: `backend/app/api/workflows.py`

- [ ] **Step 1: Add execute and run-history endpoints to `api/workflows.py`**

First, read the full current `api/workflows.py` to understand existing structure, then add the following at the bottom of the file:

```python
import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
from fastapi import Body
from fastapi.responses import StreamingResponse
from sqlalchemy import select as sa_select
from app.db.models import UserSettings, WorkflowRun
from app.workflows.executor import run_workflow


class WorkflowRunOut(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    model_config = {"from_attributes": True}


class WorkflowRunDetailOut(WorkflowRunOut):
    input_data: dict
    output_data: dict
    run_log: list


@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: uuid.UUID,
    request: Request,
    body: dict = Body(default_factory=dict),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Execute a workflow and stream per-node progress as SSE."""
    workflow = await _get_workflow_or_404(db, workflow_id, user.id)
    settings = await db.scalar(
        sa_select(UserSettings).where(UserSettings.user_id == user.id)
    )
    if not settings:
        raise HTTPException(status_code=400, detail="Settings not configured")

    input_data: dict = body.get("input", {}) if isinstance(body, dict) else {}

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in run_workflow(workflow, input_data, settings):
                import json
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            yield 'data: {"type":"cancelled"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunOut])
async def list_workflow_runs(
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkflowRun]:
    await _get_workflow_or_404(db, workflow_id, user.id)
    result = await db.execute(
        sa_select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow_id, WorkflowRun.user_id == user.id)
        .order_by(WorkflowRun.started_at.desc())
        .limit(20)
    )
    return list(result.scalars().all())


@router.get("/{workflow_id}/runs/{run_id}", response_model=WorkflowRunDetailOut)
async def get_workflow_run(
    workflow_id: uuid.UUID,
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowRun:
    await _get_workflow_or_404(db, workflow_id, user.id)
    run = await db.scalar(
        sa_select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.workflow_id == workflow_id,
            WorkflowRun.user_id == user.id,
        )
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
```

Also add the `from collections.abc import AsyncGenerator` import at the top of `workflows.py`.

- [ ] **Step 2: Wire workflow notifications**

In the `event_stream` generator inside `execute_workflow`, after the `run_done` event is yielded, add:

```python
from app.core.notifications import create_notification
if event.get("type") == "run_done":
    notif_type = "workflow_completed" if event["status"] == "completed" else "workflow_failed"
    await create_notification(
        user.id,
        notif_type,
        f"Workflow {'completed' if event['status'] == 'completed' else 'failed'}: {workflow.name}",
        f"Run {event['run_id'][:8]}... {'finished successfully' if event['status'] == 'completed' else 'failed'}.",
        action_url="/workflow-studio",
    )
```

- [ ] **Step 3: Run collect-only**

```bash
cd backend && uv run pytest --collect-only -q
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/workflows/ \
        backend/app/api/workflows.py \
        backend/app/db/models.py \
        backend/alembic/versions/*add_workflow_runs*
git commit -m "feat: add workflow execution engine with SSE streaming"
```

---

### Task 16: Frontend — Workflow execution UI

**Files:**
- Modify: `frontend/src/pages/WorkflowStudioPage.vue`

- [ ] **Step 1: Add Run button to toolbar**

Find the toolbar in `WorkflowStudioPage.vue`. Add a Run button:

```html
<button
  class="btn btn-primary"
  :disabled="!hasNodes"
  @click="openRunDrawer"
>
  {{ $t('workflow.run') }}
</button>
```

Where `hasNodes` is:
```typescript
const hasNodes = computed(() => (workflow.value?.dsl?.nodes?.length ?? 0) > 0)
```

- [ ] **Step 2: Add execution drawer state**

```typescript
const showRunDrawer = ref(false)
const runInputs = ref<Record<string, string>>({})
const runLog = ref<Array<{ node_id: string; output: string; duration_ms: number }>>([])
const runStatus = ref<'idle' | 'running' | 'completed' | 'failed'>('idle')
const activeTab = ref<'run' | 'history'>('run')
const runHistory = ref<WorkflowRun[]>([])
let abortController: AbortController | null = null

interface WorkflowRun {
  id: string
  status: string
  started_at: string
  completed_at?: string
  error_message?: string
}
```

- [ ] **Step 3: Build input form from DSL `input` nodes**

```typescript
const inputNodes = computed(() => {
  const nodes = workflow.value?.dsl?.nodes ?? []
  return nodes.filter((n: any) => n.type === 'input')
})
```

In the drawer template:
```html
<div v-if="activeTab === 'run'">
  <div v-for="node in inputNodes" :key="node.id" class="input-field">
    <label>{{ node.data.label || node.data.variable }}</label>
    <textarea v-model="runInputs[node.data.variable]" rows="2" />
  </div>
  <button
    :disabled="runStatus === 'running'"
    @click="startRun"
  >
    {{ runStatus === 'running' ? $t('workflow.running') : $t('workflow.startRun') }}
  </button>
  <button v-if="runStatus === 'running'" @click="cancelRun">
    {{ $t('workflow.cancel') }}
  </button>

  <!-- Execution log -->
  <div class="run-log">
    <div v-for="entry in runLog" :key="entry.node_id" class="log-entry">
      <span class="node-id">{{ entry.node_id }}</span>
      <span class="duration">{{ entry.duration_ms }}ms</span>
      <pre class="output">{{ entry.output }}</pre>
    </div>
  </div>
</div>
```

- [ ] **Step 4: Implement SSE streaming in `startRun`**

```typescript
async function startRun() {
  runLog.value = []
  runStatus.value = 'running'
  abortController = new AbortController()

  try {
    const response = await fetch(`/api/workflows/${workflowId}/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${authStore.token}`,
      },
      body: JSON.stringify({ input: runInputs.value }),
      signal: abortController.signal,
    })

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value)
      for (const line of chunk.split('\n')) {
        if (!line.startsWith('data: ')) continue
        const event = JSON.parse(line.slice(6))
        if (event.type === 'node_done') {
          runLog.value.push(event)
        } else if (event.type === 'run_done') {
          runStatus.value = event.status
          await fetchRunHistory()
        }
      }
    }
  } catch (err: any) {
    if (err.name !== 'AbortError') {
      runStatus.value = 'failed'
    }
  }
}

function cancelRun() {
  abortController?.abort()
  runStatus.value = 'idle'
}

async function fetchRunHistory() {
  const { data } = await api.get(`/workflows/${workflowId}/runs`)
  runHistory.value = data
}
```

- [ ] **Step 5: Add run history tab**

```html
<div v-if="activeTab === 'history'">
  <div v-for="run in runHistory" :key="run.id" class="run-history-item">
    <span :class="`status-badge status-${run.status}`">{{ run.status }}</span>
    <span>{{ new Date(run.started_at).toLocaleString() }}</span>
  </div>
</div>
```

- [ ] **Step 6: Add i18n keys**

```typescript
workflow: {
  run: '运行',
  running: '运行中...',
  startRun: '开始运行',
  cancel: '取消',
}
```

- [ ] **Step 7: Type-check**

```bash
cd frontend && bun run type-check
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/WorkflowStudioPage.vue frontend/src/locales/
git commit -m "feat: add workflow execution UI with SSE streaming and run history"
```

---

## Final Integration Check

### Task 17: Quality loop and push

- [ ] **Step 1: Run full quality loop**

```bash
cd backend
uv run ruff check --fix && uv run ruff format
uv run mypy app
docker compose -f ../docker-compose.yml up -d postgres redis
uv run pytest tests/ -x -q --tb=short
```

Fix any failures before proceeding.

- [ ] **Step 2: Frontend checks**

```bash
cd frontend
bun run lint:fix
bun run type-check
```

- [ ] **Step 3: Push**

```bash
git push origin dev
```

---

## Verification Checklist

- [ ] Changing temperature slider in Settings → chat response uses new temperature
- [ ] Creating a folder → appears in sidebar; conversation can be moved into it
- [ ] Uploading a PDF to chat → text extracted, chip shown, content sent to LLM
- [ ] Usage page shows estimated cost column and total cost card
- [ ] Completing a cron job → bell badge increments; notification appears in dropdown
- [ ] Workflow with input/llm/output nodes → Run button works; per-node progress shown in drawer
- [ ] Workflow run history tab shows past runs with status badges
