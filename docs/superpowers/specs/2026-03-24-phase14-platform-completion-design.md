# Phase 14: Platform Completion — Design Spec

**Date:** 2026-03-24
**Status:** Approved for Implementation

## Goal

Close the six most impactful functional gaps in the JARVIS platform: LLM parameter controls, conversation folders, file attachments in chat, cost estimation, in-app notifications, and workflow execution engine.

## Scope Decision

Excluded from this phase:
- OAuth/SSO (requires external provider setup; high infra cost for self-hosted deployment)
- Multi-model comparison (complex SSE multiplexing; low marginal value over existing per-conversation model switching)
- Supervisor parallelism refactor (internal optimization; user-invisible)

---

## Feature 1: LLM Parameter Controls

### Problem

`temperature` is hardcoded to `0` in `agent/llm.py`. Users cannot adjust model behavior. No `max_tokens` or `system_prompt` override is exposed in the UI.

### Design Decisions

**Storage:** Add three columns to `user_settings`. Per-conversation overrides are out of scope (YAGNI).

**New `user_settings` columns:**

| Column | Type | Default | Constraint |
|--------|------|---------|------------|
| `temperature` | FLOAT | 0.7 | NOT NULL, CHECK 0.0 ≤ x ≤ 2.0 |
| `max_tokens` | INTEGER | NULL | NULL = model default; CHECK > 0 when not NULL |
| `system_prompt` | TEXT | NULL | NULL = use persona/built-in default |

**Alembic migration:** `<hash>_add_llm_params_to_user_settings.py` (use `alembic revision --autogenerate` to generate the hash; name the file descriptively, consistent with recent migrations like `e5f6a7b8c9d0_phase13_indexes.py`).

**Backend — `api/settings.py`:**
- Make `model_provider` and `model_name` optional in `SettingsUpdate` (currently required at lines 66–67):
  ```python
  model_provider: Literal["deepseek","openai","anthropic","zhipuai","ollama"] | None = None
  model_name: str | None = Field(default=None, max_length=100)
  ```
  Update the handler (line 99–100) to only set `settings.model_provider` / `settings.model_name` when the field is in `body.model_fields_set`.
- Add three new optional fields to `SettingsUpdate`:
  ```python
  temperature: float | None = Field(default=None, ge=0.0, le=2.0)
  max_tokens: int | None = Field(default=None, gt=0)
  system_prompt: str | None = Field(default=None, max_length=4000)
  ```
- Extend the `PUT /api/settings` handler to persist these three fields when provided (same `model_fields_set` conditional-update pattern)
- Extend `GET /api/settings` response to include `temperature`, `max_tokens`, `system_prompt`

**Backend — `agent/llm.py`:**
- Change the default at line 34 from `0` to `0.7`: `kwargs.setdefault("temperature", 0.7)` (replace the `if "temperature" not in kwargs: kwargs["temperature"] = 0` block)
- `get_llm()` and `get_llm_with_fallback()` already accept `**kwargs`; no signature change required. Temperature and max_tokens flow through as kwargs from call sites.

**Backend — `agent/graph.py`:**
- Add `temperature: float = 0.7` and `max_tokens: int | None = None` params to `create_graph()` (line 118)
- Pass them explicitly at line 152: `llm = get_llm_with_fallback(provider, model, all_keys[0], base_url=base_url, temperature=temperature, max_tokens=max_tokens)`. Both land in `get_llm_with_fallback`'s `**kwargs`, then forwarded unchanged into each LLM constructor — no double-pass issue.

**Backend — `api/chat.py` — `_build_expert_graph` (line 248):**
- Add `temperature: float = 0.7` and `max_tokens: int | None = None` params to `_build_expert_graph()`
- Forward them to `create_graph()` (line ~282) and to all three expert graph creation functions (`create_code_agent_graph`, `create_research_agent_graph`, `create_writing_agent_graph`) at lines 291, 304, 318; each of those functions must also be updated to accept and forward `temperature`/`max_tokens` to their internal `create_graph()` calls (in `app/agent/experts/code_agent.py`, `app/agent/experts/research_agent.py`, and `app/agent/experts/writing_agent.py` respectively)
- At the call sites of `_build_expert_graph` (lines 668 and 990), pass `temperature=settings.temperature, max_tokens=settings.max_tokens`
- `chat_regenerate`: same treatment at line 990 (the `_build_expert_graph` call in the regenerate handler)

**Backend — `system_prompt` injection:**
The system message is currently built at two places in `chat.py`:
- Line 507: `system_msg = SystemMessage(content=build_system_prompt(llm.persona_override))` (in `chat_stream`)
- Line 902: same pattern (in `chat_regenerate`)

At both sites, apply this precedence rule: **if `user_settings.system_prompt` is set (non-NULL, non-empty), use it directly as the SystemMessage content; otherwise fall through to `build_system_prompt(llm.persona_override)` as today.** The `system_prompt` setting is raw text, not a persona ID; it takes priority over persona.

**Frontend (`SettingsPage.vue`):**
- New "Model Parameters" card below the existing model selector
- **Temperature:** slider 0.0–2.0, step 0.1, default 0.7; shows numeric value beside slider
- **Max Tokens:** number input, placeholder "Model default", min 256, max 32768; clear = NULL
- **System Prompt:** expandable `<textarea>`, placeholder "Override the assistant's default behavior…"
- All three auto-save on blur via the existing `PUT /api/settings` endpoint (extended above)

---

## Feature 2: Conversation Folders

### Problem

Users with hundreds of conversations have only pin and tag for organization. No project-based grouping exists.

### Design Decisions

**Single level only.** No nesting — adds complexity with little benefit.

**New DB model: `ConversationFolder`**
```
conversation_folders
  id            UUID PK
  user_id       UUID → users.id ON DELETE CASCADE NOT NULL
  name          VARCHAR(50) NOT NULL
  color         VARCHAR(7) NULL   -- hex e.g. "#6366f1"; NULL = default grey
  display_order INT NOT NULL DEFAULT 0
  created_at    TIMESTAMPTZ server_default NOW() NOT NULL
  updated_at    TIMESTAMPTZ server_default NOW() onupdate NOT NULL
```

**`conversations` table change:** Add `folder_id UUID NULL REFERENCES conversation_folders(id) ON DELETE SET NULL`.

**Alembic migration:** `<hash>_add_conversation_folders.py`

**API — new file `api/folders.py`** (new APIRouter with `prefix="/api/folders"`, registered in `app/main.py`):
- `GET /api/folders` — list user's folders ordered by `display_order`
- `POST /api/folders` — create: body `{ name: str, color?: str }`
- `PATCH /api/folders/{id}` — update: body `{ name?, color?, display_order? }` (all optional, update only provided fields using `model_fields_set`)
- `DELETE /api/folders/{id}` — delete; FK SET NULL automatically unfolds conversations

**Extend existing `PATCH /api/conversations/{conv_id}` in `api/conversations.py`:**
- The existing `ConversationUpdate` model (lines 49–58) currently has `title` and `persona_override`. Add:
  ```python
  folder_id: uuid.UUID | None = None
  ```
  In the handler (lines 536–543), use `"folder_id" in body.model_fields_set` to detect whether the field was explicitly included in the request body — if not in `model_fields_set`, skip the update; if in `model_fields_set` and `None`, clear the folder; if in `model_fields_set` and a UUID, assign the folder. This is standard Pydantic v2 `model_fields_set` pattern (no custom sentinel needed — `None` is a valid "clear" value, and absence from `model_fields_set` means "not provided").

**Frontend (`ChatPage.vue` sidebar):**
- Folder list section above conversation list: colored dot + name + conversation count badge
- "All" and "Pinned" remain as special non-folder views (current behavior preserved)
- Click folder → `activeFolderFilter = folder.id` → show only that folder's conversations
- Right-click conversation → "Move to folder" submenu listing all user folders plus "None" (same event pattern as existing tag context menu)
- Folder CRUD: "+" icon creates folder inline; rename on double-click; delete via context menu with confirmation toast
- Color picker: 8 preset colors (indigo, violet, rose, amber, emerald, sky, zinc, slate)
- No drag-and-drop (deferred)
- Pinia `chat.ts` store additions: `folders: Folder[]`, `activeFolderFilter: string | null`, folder CRUD actions, update `filteredConversations` computed to apply `activeFolderFilter`

---

## Feature 3: File Attachments in Chat

### Problem

Users can attach images inline but cannot attach documents for in-context analysis without going through the RAG Documents page.

### Design Decisions

**Stateless extraction — no new DB model.** Extracted text is embedded in `messages.content`. No file ID, no MinIO upload.

**Limits:** 10 MB per file; 1 file per message.

**Supported formats:** PDF, DOCX, TXT, CSV, MD.

**New endpoint `POST /api/chat/extract-file`** — added to a **new file `api/chat_files.py`** with `router = APIRouter(prefix="/api/chat", tags=["chat"])`. Register this router in `app/main.py` alongside the other routers. (The existing `chat.py` is already 1142 lines; keeping file extraction separate maintains modularity.)

Endpoint details:
- Multipart upload: `file` field (UploadFile)
- Auth: `get_current_user`; rate limit: 10/minute
- File size check: reject `> 10 MB` with HTTP 413
- MIME type check: accept `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain`, `text/csv`, `text/markdown`; reject others with HTTP 415
- Extraction:
  - PDF → `pypdf` (already a dependency in `backend/pyproject.toml`)
  - DOCX → `python-docx` (already a dependency in `backend/pyproject.toml`)
  - TXT / CSV / MD → UTF-8 decode with `errors="replace"`
- Truncate extracted text to 30 000 characters if longer
- Response: `{ filename: str, char_count: int, extracted_text: str }`
- HTTP 422 if extraction fails

**`ChatRequest` change in `api/chat.py`:** Add optional field:
```python
class FileContext(BaseModel):
    filename: str = Field(max_length=255)
    extracted_text: str = Field(max_length=30_000)

# In ChatRequest:
file_context: FileContext | None = None
```

**`chat_stream` change:** If `file_context` is present, prepend to the `content` parameter passed to `Message(role="human", content=...)` before the DB insert:
```
[Attached file: {filename}]
{extracted_text}

---
{user_message}
```
No schema migration needed — stored in the existing `messages.content` TEXT column.

**Frontend (`ChatPage.vue`):**
- Extend the existing paperclip `<input accept="image/*">` to also accept `.pdf,.docx,.txt,.csv,.md`
- File type routing on selection: `image/*` → existing base64 flow; documents → `POST /api/chat/extract-file`
- Upload state: spinner chip while extracting; success → chip shows filename + char count; error → toast
- File chip displayed above input alongside image thumbnails
- Only one document per message; adding a second replaces the first with a confirmation
- On send: `file_context` in the request body populated from the extraction response

---

## Feature 4: Cost Estimation

### Problem

The usage page shows token counts but gives no sense of monetary cost.

### Design Decisions

**Static price table in backend — no DB storage.** Cost computed at query time from existing `tokens_input` / `tokens_output` fields. Zero DB migration.

**New file `app/core/pricing.py`:**

```python
# USD per 1 million tokens: (input_price, output_price)
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
    },
    "zhipuai": {
        "glm-4": (0.10, 0.10),
        "glm-4-flash": (0.00, 0.00),
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

**`api/usage.py` change:**
- Import `estimate_cost` from `app.core.pricing`
- Add `Message.model_name` to the `SELECT` and `GROUP BY` in the query (line 33–50). Current query groups by `(date, model_provider)` only; extend to `(date, model_provider, model_name)`. This is required so `estimate_cost(provider, model, ...)` receives the model identifier (e.g., `"gpt-4o"`, `"deepseek-chat"`).
- Add `estimated_cost_usd: float` to each daily row: `estimate_cost(r.model_provider or "", r.model_name or "", r.tokens_in, r.tokens_out)`
- Add `total_estimated_cost_usd: float` to the top-level response (sum of all daily rows)

**Frontend (`UsagePage.vue`):**
- New summary card: "Estimated Cost" (alongside existing token total cards)
- Table: new cost column; format `$0.0042` (4 sig figs); `< $0.0001` for sub-cent values
- Disclaimer: "Estimates based on public list pricing. Actual costs may differ."

---

## Feature 5: In-App Notification System

### Problem

Async operations (cron job completion, webhook delivery failures, workspace invitations, workflow results) have no feedback channel.

### Design Decisions

**Polling every 30 seconds — not SSE.** Sufficient latency for all notification types; no new server-side streaming infrastructure.

**New DB model: `Notification`**
```
notifications
  id            UUID PK
  user_id       UUID → users.id ON DELETE CASCADE NOT NULL
  type          VARCHAR(50) NOT NULL
                  allowed: cron_completed | cron_failed | webhook_failed |
                           invitation_received | workflow_completed | workflow_failed
  title         VARCHAR(100) NOT NULL
  body          VARCHAR(500) NOT NULL
  is_read       BOOLEAN NOT NULL DEFAULT false
  action_url    VARCHAR(200) NULL   -- frontend Vue Router path, e.g. "/cron"
  metadata_json JSONB NOT NULL DEFAULT {}
  created_at    TIMESTAMPTZ server_default NOW() NOT NULL

INDEX: (user_id, is_read, created_at DESC)
```

**Alembic migration:** `<hash>_add_notifications.py`

**New helper `app/core/notifications.py`:**
```python
async def create_notification(
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str,
    *,
    action_url: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Insert a notification with its own AsyncSessionLocal session.

    Same pattern as log_action() in app/core/audit.py — call-and-forget,
    safe to call from worker.py and API handlers.
    """
```

**New router `api/notifications.py`** (registered in `app/main.py`):
- `GET /api/notifications?unread_only=false&limit=20` — list (ordered by `created_at DESC`)
- `GET /api/notifications/unread-count` — `{ count: int }` (polling target)
- `PATCH /api/notifications/{id}/read` — mark single notification as read
- `POST /api/notifications/read-all` — mark all as read
- `DELETE /api/notifications/{id}` — delete a notification

**Notification creation points:**

| File | Function | Trigger | Notification type |
|------|----------|---------|-------------------|
| `worker.py` | `execute_cron_job` | Job finishes successfully | `cron_completed` |
| `worker.py` | `execute_cron_job` | Job raises an exception | `cron_failed` |
| `worker.py` | `deliver_webhook` | `final_status == "failed"` AND `attempt >= len(_WEBHOOK_RETRY_DELAYS)` (fires when `attempt >= 2`; no further retry queued). The line-185 `if final_status == "failed" and attempt < len(...)` block handles retryable failures (raises to queue retry). The notification fires in the **else path** of that block — i.e., after the `if/raise` block exits — guarded by `if final_status == "failed"`, before the `logger.info("deliver_webhook_done")` call. | `webhook_failed` |
| `api/invitations.py` | `invite_member` (line 45) | Invited email belongs to an existing registered user | `invitation_received` |
| `api/workflows.py` | `execute_workflow` (new, Feature 6) | Run completes successfully | `workflow_completed` |
| `api/workflows.py` | `execute_workflow` (new, Feature 6) | Run fails | `workflow_failed` |

**Frontend:**
- Bell icon in header (top-right area, currently absent), red badge showing unread count (hidden when 0)
- Dropdown panel: last 10 notifications; "Mark all read" button
- Polling: `setInterval(fetchUnreadCount, 30_000)` on mount; poll immediately on `document.visibilitychange` when tab becomes active
- Click notification: mark as read + `router.push(action_url)` if `action_url` is set
- New Pinia store `notification.ts`: `notifications: Notification[]`, `unreadCount: number`, `fetchNotifications()`, `fetchUnreadCount()`, `markRead(id)`, `markAllRead()`

---

## Feature 6: Workflow Execution Engine

### Problem

`WorkflowStudioPage.vue` has a visual node editor that saves/loads the DSL, but there is no execution endpoint. Workflows cannot be run.

### Design Decisions

**DSL schema** (stored in existing `workflows.dsl` JSONB field — same column, extended semantics):

```json
{
  "nodes": [
    { "id": "n1", "type": "input",     "data": { "variable": "user_input", "label": "User Input" } },
    { "id": "n2", "type": "llm",       "data": { "prompt": "Summarize: {{user_input}}", "model_override": null } },
    { "id": "n3", "type": "tool",      "data": { "tool_name": "search", "params": {} } },
    { "id": "n4", "type": "condition", "data": { "left": "{{n2.output}}", "operator": "contains", "right": "error" } },
    { "id": "n5", "type": "output",    "data": { "value": "{{n2.output}}" } }
  ],
  "edges": [
    { "id": "e1", "source": "n1", "target": "n2" },
    { "id": "e2", "source": "n2", "target": "n5" }
  ]
}
```

Supported node types: `input`, `output`, `llm`, `tool`, `condition`.

Variable interpolation: `{{variable_name}}` or `{{node_id.output}}` — resolved via a small regex helper in `executor.py` (NOT `str.format_map()`; double-brace syntax is chosen to avoid conflicts with literal `{` and `}` characters common in LLM prompts):

```python
import re

def _interpolate(template: str, context: dict) -> str:
    """Replace {{key}} and {{node_id.output}} with values from context."""
    def _replace(m: re.Match) -> str:
        key = m.group(1)          # e.g. "user_input" or "n2.output"
        parts = key.split(".", 1) # ["n2", "output"] or ["user_input"]
        val = context.get(parts[0]) if len(parts) == 1 else (context.get(parts[0]) or {}).get(parts[1], "")
        return str(val) if val is not None else ""
    return re.sub(r"\{\{([\w.]+)\}\}", _replace, template)
```

**Condition node security:** Explicit operator dispatch only (`contains`, `equals`, `startswith`, `endswith`, `gt`, `lt`) — **no dynamic code evaluation of any kind**. Unknown operators default to `True` (non-blocking).

**New DB model: `WorkflowRun`**
```
workflow_runs
  id              UUID PK
  workflow_id     UUID → workflows.id ON DELETE CASCADE NOT NULL
  user_id         UUID → users.id ON DELETE CASCADE NOT NULL
  status          VARCHAR(20) NOT NULL CHECK IN ('pending','running','completed','failed')
  input_data      JSONB NOT NULL DEFAULT {}
  output_data     JSONB NOT NULL DEFAULT {}
  error_message   TEXT NULL
  run_log         JSONB NOT NULL DEFAULT []
                  -- list of { node_id: str, status: str, output: str, duration_ms: int, timestamp: str }
  started_at      TIMESTAMPTZ NOT NULL server_default NOW()
  completed_at    TIMESTAMPTZ NULL
```

**Alembic migration:** `<hash>_add_workflow_runs.py`

**New Python package `app/workflows/`** — create as a proper package with `app/workflows/__init__.py` (empty). Contains `app/workflows/executor.py`.

**`app/workflows/executor.py`:**
```python
async def run_workflow(
    workflow: Workflow,
    input_data: dict,
    user_settings: UserSettings,   # ORM model from app.db.models, post-Feature-1
) -> AsyncGenerator[dict, None]:
    ...
```

- Import `_TOOL_MAP` directly from `app.agent.graph` (the module-private convention is advisory; this cross-module import is acceptable here; documented at the import site with a comment)
- Topological sort via Kahn's algorithm; raises `ValueError` on cycle detection
- Safety limits: max 50 nodes; max 5-minute wall-clock via `asyncio.wait_for`
- Per-node execution:
  - `input`: bind `input_data[variable]` into context dict
  - `output`: resolve `{{...}}` templates via `_interpolate(template, context)`; emit as final result
  - `llm`: interpolate prompt via `_interpolate`; call LLM using `user_settings.model_provider`, `.model_name`, `.temperature`, `.max_tokens` (added in Feature 1); uses `get_llm_with_fallback` from `app.agent.llm`
  - `tool`: look up by `tool_name` in `_TOOL_MAP`; invoke with resolved `params` dict
  - `condition`: operator dispatch on resolved `left`/`right` string values
- Each completed node yields: `{ "type": "node_done", "node_id": str, "output": str, "duration_ms": int }`
- On completion: yields `{ "type": "run_done", "run_id": str, "status": "completed"|"failed" }`
- Updates `WorkflowRun` record in DB at start and at end

**API additions to `api/workflows.py`:**
- `POST /api/workflows/{id}/execute` — SSE `StreamingResponse`; creates `WorkflowRun` (status=running); body: `{ input: dict }` (optional)
- `GET /api/workflows/{id}/runs` — list last 20 runs for this workflow
- `GET /api/workflows/{id}/runs/{run_id}` — full run detail with `run_log`

**Frontend (`WorkflowStudioPage.vue`):**
- "Run" button in toolbar (disabled when 0 nodes)
- Clicking "Run" opens a right-side execution drawer panel
- Input form: one text field per `input` node (keyed by `variable`; `label` used as form label)
- SSE stream consumed on submission; completed nodes get a green checkmark overlay in the VueFlow canvas
- Execution log: scrollable list of node ID + output in the drawer
- "Run History" tab: list of past `WorkflowRun` rows with status badge, started_at, duration
- Cancel: `AbortController.abort()` disconnects SSE; backend catches `asyncio.CancelledError` and marks run as `failed`

---

## Implementation Order and Migration Summary

| Order | Feature | Migration | New backend files | Key existing files touched |
|-------|---------|-----------|-------------------|---------------------------|
| 1 | LLM Parameter Controls | `<hash>_add_llm_params_to_user_settings.py` | — | `api/settings.py`, `agent/llm.py`, `agent/graph.py`, `agent/experts/code_agent.py`, `agent/experts/research_agent.py`, `agent/experts/writing_agent.py`, `api/chat.py` |
| 2 | Conversation Folders | `<hash>_add_conversation_folders.py` | `api/folders.py` | `api/conversations.py`, `main.py`, `db/models.py` |
| 3 | File Attachments | none | `api/chat_files.py` | `api/chat.py`, `main.py` |
| 4 | Cost Estimation | none | `core/pricing.py` | `api/usage.py` |
| 5 | Notification System | `<hash>_add_notifications.py` | `api/notifications.py`, `core/notifications.py` | `worker.py`, `api/invitations.py`, `main.py`, `db/models.py` |
| 6 | Workflow Execution | `<hash>_add_workflow_runs.py` | `workflows/__init__.py`, `workflows/executor.py` | `api/workflows.py`, `main.py`, `db/models.py` |

Migration file naming convention: follow recent project pattern (`<alembic_hash>_<short_description>.py`) — use `alembic revision --autogenerate -m "<description>"` to generate files with correct hash prefixes and `down_revision` chains.

---

## What This Does NOT Cover

- OAuth/SSO login
- Multi-model parallel comparison
- Folder nesting (single level only)
- Per-conversation LLM parameter overrides (global settings only)
- Workflow node types beyond: input, output, llm, tool, condition
- File attachment storage (text extracted inline; not stored as files)
- Real-time notification push (polling only, 30-second interval)
- Workflow parallel branch execution (sequential only in this phase)

## Dependencies Between Features

Feature 6 (Workflow Execution) depends on Feature 1 (LLM Parameter Controls) because the workflow executor reads `user_settings.temperature` and `user_settings.max_tokens`. Implement Feature 1 before Feature 6. All other features are independent of each other.

## Success Criteria

1. Temperature/max_tokens/system_prompt in Settings affect chat responses
2. Users can create folders and assign conversations to them via right-click menu
3. PDF/DOCX/TXT files can be attached to chat messages for inline analysis
4. Usage page shows estimated USD cost alongside token counts
5. Bell icon shows unread count; cron/webhook/workflow events create notifications
6. Workflows can be executed with a Run button; per-node progress visible in the canvas
