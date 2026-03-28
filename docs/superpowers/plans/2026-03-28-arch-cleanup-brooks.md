# Architecture Cleanup (Brooks-Lint Audit) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 6 architecture problems identified in the Brooks-Lint audit: Pydantic style inconsistency, core↔db layering violation, chat.py god file, models.py god file, circular import documentation, and exception handling.

**Architecture:** Mechanical standardizations first (low risk), then structural decompositions (medium risk), so each task independently passes tests. No behavioral changes — pure refactoring.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x, Pydantic v2, pytest+anyio

---

## File Map

**Created:**
- `backend/app/services/audit.py` (moved from core/)
- `backend/app/services/notifications.py` (moved from core/)
- `backend/tests/services/__init__.py`
- `backend/tests/services/test_audit.py` (moved from tests/core/)
- `backend/app/db/models/__init__.py`
- `backend/app/db/models/user.py`
- `backend/app/db/models/conversation.py`
- `backend/app/db/models/document.py`
- `backend/app/db/models/scheduler.py`
- `backend/app/db/models/organization.py`
- `backend/app/db/models/plugin.py`
- `backend/app/db/models/misc.py` (Notification, AuditLog, UserMemory, Persona)
- `backend/app/api/chat/__init__.py`
- `backend/app/api/chat/schemas.py`
- `backend/app/api/chat/sse.py`
- `backend/app/api/chat/message_builder.py`
- `backend/app/api/chat/graph_builder.py`
- `backend/app/api/chat/tool_loader.py`
- `backend/app/api/chat/routes.py`

**Deleted:**
- `backend/app/core/audit.py`
- `backend/app/core/notifications.py`
- `backend/app/db/models.py` (replaced by package)
- `backend/app/api/chat.py` (replaced by package)
- `backend/tests/core/test_audit.py` (moved to tests/services/)

**Modified:**
- `backend/app/api/auth.py` — import path: `core.audit` → `services.audit`
- `backend/app/api/invitations.py` — import path: `core.notifications` → `services.notifications`
- `backend/app/worker.py` — import path: `core.notifications` → `services.notifications`
- `backend/app/workflows/executor.py` — import path: `core.notifications` → `services.notifications`
- `backend/app/api/auth.py` — Pydantic ConfigDict
- `backend/app/api/conversations.py` — Pydantic ConfigDict
- `backend/app/api/documents.py` — Pydantic ConfigDict
- `backend/app/api/folders.py` — Pydantic ConfigDict
- `backend/app/api/memory.py` — Pydantic ConfigDict
- `backend/app/api/notifications.py` — Pydantic ConfigDict
- `backend/app/api/plugins.py` — Pydantic ConfigDict
- `backend/app/api/public.py` — Pydantic ConfigDict
- `backend/app/api/webhooks.py` — Pydantic ConfigDict
- `backend/app/api/workflows.py` — Pydantic ConfigDict
- `backend/app/api/personas.py` — already ConfigDict, no change needed
- `backend/app/tools/subagent_tool.py` — add architecture docstring
- `backend/app/agent/graph.py` — add architecture docstring
- Various API files — exception handling improvements

---

## Task 1: Standardize Pydantic model_config to ConfigDict

**Files:**
- Modify: `backend/app/api/auth.py` (ProfileOut — missing model_config)
- Modify: `backend/app/api/conversations.py` (ConversationOut, MessageOut)
- Modify: `backend/app/api/documents.py` (DocumentOut)
- Modify: `backend/app/api/folders.py` (FolderOut)
- Modify: `backend/app/api/memory.py` (MemoryOut)
- Modify: `backend/app/api/notifications.py` (NotificationOut)
- Modify: `backend/app/api/plugins.py` (InstalledPluginOut)
- Modify: `backend/app/api/public.py` (PublicMessageOut, PublicConversationOut — missing)
- Modify: `backend/app/api/webhooks.py` (WebhookOut, WebhookDeliveryOut)
- Modify: `backend/app/api/workflows.py` (WorkflowOut — WorkflowRunOut already uses ConfigDict)
- Modify: `backend/app/services/skill_market.py` (MarketSkillOut — missing model_config)

- [ ] **Step 1: Add/update ConfigDict in all Out model classes**

In every file listed, ensure:
1. `from pydantic import ConfigDict` is in the import block (add if missing)
2. Every `Out` Pydantic class has `model_config = ConfigDict(from_attributes=True)`
3. Remove `{"from_attributes": True}` dict-literal style
4. Remove `from pydantic import BaseModel, Field` if ConfigDict wasn't previously imported — add ConfigDict there instead

Pattern to apply uniformly:

```python
# Before (dict literal style — remove this)
model_config = {"from_attributes": True}

# After (ConfigDict style — use this everywhere)
from pydantic import BaseModel, ConfigDict, Field  # add ConfigDict to existing import

model_config = ConfigDict(from_attributes=True)
```

Specific files and classes:

`api/auth.py`: `ProfileOut` is missing model_config entirely. Add:
```python
# In ProfileOut class body:
model_config = ConfigDict(from_attributes=True)
```
And add `ConfigDict` to pydantic imports.

`api/conversations.py`: Change `ConversationOut` and `MessageOut`:
```python
model_config = ConfigDict(from_attributes=True)
```

`api/documents.py`: Change `DocumentOut`:
```python
model_config = ConfigDict(from_attributes=True)
```

`api/folders.py`: Change `FolderOut`:
```python
model_config = ConfigDict(from_attributes=True)
```

`api/memory.py`: Change `MemoryOut`:
```python
model_config = ConfigDict(from_attributes=True)
```

`api/notifications.py`: Change `NotificationOut`:
```python
model_config = ConfigDict(from_attributes=True)
```

`api/plugins.py`: Change `InstalledPluginOut` and `MarketSkillOut` (if in this file):
```python
model_config = ConfigDict(from_attributes=True)
```

`api/public.py`: Change `PublicMessageOut`. Add to `PublicConversationOut` (missing):
```python
model_config = ConfigDict(from_attributes=True)
```

`api/webhooks.py`: Change `WebhookOut` and `WebhookDeliveryOut`:
```python
model_config = ConfigDict(from_attributes=True)
```

`api/workflows.py`: Change `WorkflowOut` (WorkflowRunOut already correct):
```python
model_config = ConfigDict(from_attributes=True)
```

`services/skill_market.py`: `MarketSkillOut` is missing model_config. Add:
```python
model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 2: Verify no dict-literal style remains**

```bash
cd backend
grep -rn 'model_config = {' app/api/ app/services/
```

Expected: no output.

- [ ] **Step 3: Run import check**

```bash
cd backend
uv run pytest --collect-only -q 2>&1 | tail -5
```

Expected: collection succeeds, no import errors.

- [ ] **Step 4: Commit**

```bash
cd backend
git add app/api/ app/services/
git commit -m "refactor: standardize all Pydantic Out models to use ConfigDict(from_attributes=True)"
```

---

## Task 2: Move core/audit.py → services/audit.py (fix layering violation)

**Problem:** `core/audit.py` imports `app.db.models` and `app.db.session`. Core should not depend on db. This function is a service (it writes data), not a cross-cutting concern.

**Files:**
- Create: `backend/app/services/audit.py`
- Delete: `backend/app/core/audit.py`
- Modify: `backend/app/api/auth.py` (1 import change)
- Move+Modify: `backend/tests/core/test_audit.py` → `backend/tests/services/test_audit.py`
- Create: `backend/tests/services/__init__.py`

- [ ] **Step 1: Create services/audit.py with identical content**

```python
# backend/app/services/audit.py
"""Audit log service — persists security-relevant user actions to the database."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog

from app.core.limiter import get_trusted_client_ip
from app.db.models import AuditLog
from app.db.session import AsyncSessionLocal

if TYPE_CHECKING:
    from fastapi import Request

logger = structlog.get_logger(__name__)


async def log_action(
    action: str,
    *,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request: Request | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Persist an audit log entry asynchronously.

    Failures are swallowed and logged — audit logging must never break the
    primary request path.
    """
    ip_address: str | None = None
    user_agent: str | None = None
    if request is not None:
        ip_address = get_trusted_client_ip(request)
        raw_ua = request.headers.get("user-agent", "")
        user_agent = raw_ua[:1000] or None

    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                session.add(
                    AuditLog(
                        user_id=user_id,
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        extra=extra,
                    )
                )
    except Exception:
        logger.warning(
            "audit_log_failed",
            action=action,
            user_id=str(user_id) if user_id else None,
            exc_info=True,
        )
```

- [ ] **Step 2: Update api/auth.py import**

Find line `from app.core.audit import log_action` and change to:
```python
from app.services.audit import log_action
```

- [ ] **Step 3: Delete core/audit.py**

```bash
cd backend
rm app/core/audit.py
```

- [ ] **Step 4: Create tests/services/__init__.py**

```bash
touch backend/tests/services/__init__.py
```

- [ ] **Step 5: Move and update test file**

Create `backend/tests/services/test_audit.py` with the contents of `backend/tests/core/test_audit.py`, but with these changes:
- `from app.core.audit import log_action` → `from app.services.audit import log_action`
- All `patch("app.core.audit.AsyncSessionLocal", ...)` → `patch("app.services.audit.AsyncSessionLocal", ...)`

Then delete `backend/tests/core/test_audit.py`.

- [ ] **Step 6: Run audit tests**

```bash
cd backend
uv run pytest tests/services/test_audit.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Run full test collect**

```bash
cd backend
uv run pytest --collect-only -q 2>&1 | tail -5
```

Expected: no import errors.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/audit.py backend/app/api/auth.py \
        backend/tests/services/ backend/tests/core/test_audit.py
git commit -m "refactor: move audit service from core/ to services/ to fix layering violation"
```

---

## Task 3: Move core/notifications.py → services/notifications.py (fix layering violation)

**Problem:** `core/notifications.py` imports `app.db.models` and `app.db.session`. Same issue as audit.py.

**Files:**
- Create: `backend/app/services/notifications.py`
- Delete: `backend/app/core/notifications.py`
- Modify: `backend/app/api/invitations.py` (1 import)
- Modify: `backend/app/worker.py` (1 import)
- Modify: `backend/app/workflows/executor.py` (1 import, inside function body)

- [ ] **Step 1: Create services/notifications.py with identical content**

```python
# backend/app/services/notifications.py
"""Notification service — creates persistent in-app notifications."""

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)


async def create_notification(
    user_id: uuid.UUID | str,
    type: str,
    title: str,
    body: str,
    *,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
    db: AsyncSession | None = None,
) -> uuid.UUID:
    """Create a persistent in-app notification for a user.

    If an existing session 'db' is provided, it will be used.
    Otherwise, a new short-lived session is created.
    """
    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id

    if db:
        notification = Notification(
            user_id=u_id,
            type=type,
            title=title,
            body=body,
            action_url=action_url,
            metadata_json=metadata or {},
        )
        db.add(notification)
        await db.flush()
        notification_id = notification.id
    else:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                notification = Notification(
                    user_id=u_id,
                    type=type,
                    title=title,
                    body=body,
                    action_url=action_url,
                    metadata_json=metadata or {},
                )
                session.add(notification)
                await session.flush()
                notification_id = notification.id

    logger.info(
        "notification_created",
        user_id=str(u_id),
        type=type,
        notification_id=str(notification_id),
    )
    return notification_id
```

- [ ] **Step 2: Update api/invitations.py**

Find `from app.core.notifications import create_notification` → change to:
```python
from app.services.notifications import create_notification
```

- [ ] **Step 3: Update worker.py**

Find `from app.core.notifications import create_notification` → change to:
```python
from app.services.notifications import create_notification
```

- [ ] **Step 4: Update workflows/executor.py**

This import is inside a function body (line ~266). Find and change:
```python
from app.core.notifications import create_notification
```
→
```python
from app.services.notifications import create_notification
```

- [ ] **Step 5: Delete core/notifications.py**

```bash
cd backend
rm app/core/notifications.py
```

- [ ] **Step 6: Run import check and tests**

```bash
cd backend
uv run pytest --collect-only -q 2>&1 | tail -5
uv run pytest tests/api/test_notifications.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/notifications.py backend/app/api/invitations.py \
        backend/app/worker.py backend/app/workflows/executor.py
git commit -m "refactor: move notifications service from core/ to services/ to fix layering violation"
```

---

## Task 4: Split db/models.py into db/models/ package

**Goal:** Replace the 1055-line monolithic models.py with a domain-organized package. All existing imports (`from app.db.models import X`) continue to work unchanged because `__init__.py` re-exports everything.

**SQLAlchemy note:** SQLAlchemy 2.x resolves `Mapped["ClassName"]` string annotations via the mapper registry. All model files import the same `Base`, so cross-file relationships work as long as all files are imported before queries run (guaranteed by `__init__.py`).

**Files:**
- Create: `backend/app/db/models/` (directory)
- Create: `backend/app/db/models/__init__.py`
- Create: `backend/app/db/models/user.py`
- Create: `backend/app/db/models/conversation.py`
- Create: `backend/app/db/models/document.py`
- Create: `backend/app/db/models/scheduler.py`
- Create: `backend/app/db/models/organization.py`
- Create: `backend/app/db/models/plugin.py`
- Create: `backend/app/db/models/misc.py`
- Delete: `backend/app/db/models.py`

**Domain grouping:**
- `user.py`: UserRole, User, UserSettings, ApiKey
- `conversation.py`: Conversation, ConversationFolder, ConversationTag, Message, AgentSession, SharedConversation
- `document.py`: Document
- `scheduler.py`: CronJob, JobExecution, Webhook, WebhookDelivery
- `organization.py`: Organization, Workspace, WorkspaceMember, WorkspaceSettings, Invitation
- `plugin.py`: InstalledPlugin, PluginConfig
- `misc.py`: UserMemory, AuditLog, Notification, Persona, Workflow, WorkflowRun

- [ ] **Step 1: Read the full models.py to identify exact class boundaries**

```bash
cd backend
grep -n "^class " app/db/models.py
```

Expected output (find exact line numbers for each class to guide the split).

- [ ] **Step 2: Create db/models/ directory**

```bash
mkdir -p backend/app/db/models
```

- [ ] **Step 3: Create user.py**

Extract UserRole enum, User, UserSettings, ApiKey classes with their imports. Each domain file needs:
```python
import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (Boolean, DateTime, ForeignKey, Integer, String, Text, func)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.permissions import DEFAULT_ENABLED_TOOLS
from app.db.base import Base
```

Include only the imports needed by the classes in that file.

- [ ] **Step 4: Create conversation.py**

Extract Conversation, ConversationFolder, ConversationTag, Message, AgentSession, SharedConversation.

Required imports:
```python
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
```

- [ ] **Step 5: Create document.py**

Extract Document class only.

- [ ] **Step 6: Create scheduler.py**

Extract CronJob, JobExecution, Webhook, WebhookDelivery.

- [ ] **Step 7: Create organization.py**

Extract Organization, Workspace, WorkspaceMember, WorkspaceSettings, Invitation.

Note: Organization has a circular FK with User (`use_alter=True` in User model). The string-based relationship ref handles this cleanly.

- [ ] **Step 8: Create plugin.py**

Extract InstalledPlugin, PluginConfig.

- [ ] **Step 9: Create misc.py**

Extract UserMemory, AuditLog, Notification, Persona, Workflow, WorkflowRun.

- [ ] **Step 10: Create __init__.py that re-exports everything**

```python
# backend/app/db/models/__init__.py
"""Database models package — imports all domain model files to register them with SQLAlchemy mapper."""

from app.db.models.conversation import (
    AgentSession,
    Conversation,
    ConversationFolder,
    ConversationTag,
    Message,
    SharedConversation,
)
from app.db.models.document import Document
from app.db.models.misc import AuditLog, Notification, Persona, UserMemory, Workflow, WorkflowRun
from app.db.models.organization import (
    Invitation,
    Organization,
    Workspace,
    WorkspaceMember,
    WorkspaceSettings,
)
from app.db.models.plugin import InstalledPlugin, PluginConfig
from app.db.models.scheduler import CronJob, JobExecution, Webhook, WebhookDelivery
from app.db.models.user import ApiKey, User, UserRole, UserSettings

__all__ = [
    # user
    "UserRole",
    "User",
    "UserSettings",
    "ApiKey",
    # conversation
    "Conversation",
    "ConversationFolder",
    "ConversationTag",
    "Message",
    "AgentSession",
    "SharedConversation",
    # document
    "Document",
    # scheduler
    "CronJob",
    "JobExecution",
    "Webhook",
    "WebhookDelivery",
    # organization
    "Organization",
    "Workspace",
    "WorkspaceMember",
    "WorkspaceSettings",
    "Invitation",
    # plugin
    "InstalledPlugin",
    "PluginConfig",
    # misc
    "UserMemory",
    "AuditLog",
    "Notification",
    "Persona",
    "Workflow",
    "WorkflowRun",
]
```

- [ ] **Step 11: Delete the old models.py**

```bash
cd backend
rm app/db/models.py
```

- [ ] **Step 12: Run import and collection check**

```bash
cd backend
uv run pytest --collect-only -q 2>&1 | tail -10
```

Expected: no import errors. All tests collected.

- [ ] **Step 13: Run database model tests**

```bash
cd backend
uv run pytest tests/db/ -v
```

Expected: all pass.

- [ ] **Step 14: Commit**

```bash
git add backend/app/db/models/ backend/app/db/models.py
git commit -m "refactor: split db/models.py into domain-organized package (user/conversation/document/scheduler/organization/plugin/misc)"
```

---

## Task 5: Split api/chat.py into api/chat/ package

**Goal:** Decompose the 1223-line god file into 6 focused modules. All existing imports (`from app.api.chat import X`) continue to work because `__init__.py` re-exports everything currently used by tests and `main.py`.

**Modules:**
- `schemas.py`: ChatRequest, RegenerateRequest, FileContext (Pydantic models)
- `sse.py`: _format_sse, _sse_events_from_chunk (SSE encoding)
- `message_builder.py`: _build_memory_message, _walk_message_chain, _build_langchain_messages, _build_message_kwargs, _build_tool_message_kwargs, _tool_call_signature, _serialize_tool_message, _extract_token_counts, _ROLE_TO_MESSAGE, _MEMORY_PROMPT_LIMIT, _MEMORY_CHAR_LIMIT
- `graph_builder.py`: _build_expert_graph
- `tool_loader.py`: _load_personal_plugin_tools, _load_tools
- `routes.py`: router, chat_stream, chat_regenerate (imports from all above)
- `__init__.py`: re-exports everything tests/main.py need

**Files:**
- Create: `backend/app/api/chat/` (directory)
- Create: `backend/app/api/chat/__init__.py`
- Create: `backend/app/api/chat/schemas.py`
- Create: `backend/app/api/chat/sse.py`
- Create: `backend/app/api/chat/message_builder.py`
- Create: `backend/app/api/chat/graph_builder.py`
- Create: `backend/app/api/chat/tool_loader.py`
- Create: `backend/app/api/chat/routes.py`
- Delete: `backend/app/api/chat.py`

- [ ] **Step 1: Create api/chat/ directory**

```bash
mkdir -p backend/app/api/chat
```

- [ ] **Step 2: Create schemas.py**

```python
# backend/app/api/chat/schemas.py
"""Request/response schemas for the chat API."""

import uuid

from pydantic import BaseModel, Field, field_validator


class FileContext(BaseModel):
    """File context carried within a conversation (text already extracted)."""

    filename: str = Field(max_length=255)
    extracted_text: str = Field(max_length=30_000)


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    content: str = Field(min_length=1, max_length=50000)
    image_urls: list[str] | None = None
    workspace_id: uuid.UUID | None = None
    parent_message_id: uuid.UUID | None = None
    persona_id: uuid.UUID | None = None
    workflow_dsl: dict | None = None
    model_override: str | None = Field(None, max_length=100)
    file_context: FileContext | None = None

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if len(v) > 4:
            raise ValueError("Maximum 4 images per message")
        for url in v:
            if len(url) > 5_600_000:
                raise ValueError("Image too large (max 4 MB per image)")
        return v


class RegenerateRequest(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    workspace_id: uuid.UUID | None = None
    model_override: str | None = Field(None, max_length=100)
```

- [ ] **Step 3: Create sse.py**

```python
# backend/app/api/chat/sse.py
"""SSE encoding utilities for the chat streaming API."""

import json
import uuid


def _format_sse(payload: dict) -> str:
    """Encode a dict as an SSE data line."""
    return "data: " + json.dumps(payload) + "\n\n"


def _sse_events_from_chunk(
    chunk: dict,
    full_content: str,
    human_msg_id: uuid.UUID | None = None,
) -> tuple[list[str], str]:
    """Convert a LangGraph stream chunk into SSE event lines.

    Returns (list_of_sse_lines, updated_full_content).
    """
    events: list[str] = []

    if "approval" in chunk:
        pending = chunk["approval"]["pending_tool_call"]
        if pending is not None:
            events.append(
                _format_sse(
                    {
                        "type": "approval_required",
                        "tool": pending["name"],
                        "args": pending.get("args", {}),
                        "human_msg_id": str(human_msg_id) if human_msg_id else None,
                    }
                )
            )
    elif "llm" in chunk:
        ai_msg = chunk["llm"]["messages"][-1]
        if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
            for tc in ai_msg.tool_calls:
                events.append(
                    _format_sse(
                        {
                            "type": "tool_start",
                            "tool": tc["name"],
                            "args": tc.get("args", {}),
                        }
                    )
                )

        new_content = ai_msg.content
        delta = new_content[len(full_content):]
        full_content = new_content
        if delta:
            events.append(
                _format_sse({"type": "delta", "delta": delta, "content": full_content})
            )
    elif "tools" in chunk:
        for tm in chunk["tools"]["messages"]:
            events.append(
                _format_sse(
                    {
                        "type": "tool_end",
                        "tool": tm.name,
                        "result_preview": tm.content[:200],
                    }
                )
            )
    return events, full_content
```

- [ ] **Step 4: Create message_builder.py**

```python
# backend/app/api/chat/message_builder.py
"""Message construction utilities — converts DB messages to LangChain format."""

import json
import uuid
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, UserMemory

logger = structlog.get_logger(__name__)

_ROLE_TO_MESSAGE = {
    "human": HumanMessage,
    "ai": AIMessage,
    "tool": ToolMessage,
    "system": SystemMessage,
}

_MEMORY_PROMPT_LIMIT = 100
_MEMORY_CHAR_LIMIT = 8000


async def _build_memory_message(
    db: AsyncSession, user_id: uuid.UUID
) -> SystemMessage | None:
    """Load user memories and return a SystemMessage for prompt injection, or None."""
    rows = await db.scalars(
        select(UserMemory)
        .where(UserMemory.user_id == user_id)
        .order_by(UserMemory.category, UserMemory.key)
        .limit(_MEMORY_PROMPT_LIMIT)
    )
    memories = list(rows.all())

    lines: list[str] = []
    total_chars = 0
    for m in reversed(memories):
        line = f"- [{m.category}] {m.key}: {m.value}"
        if total_chars + len(line) > _MEMORY_CHAR_LIMIT:
            break
        lines.append(line)
        total_chars += len(line)

    if not lines:
        return None

    block = "## 用户个人记忆（跨对话持久化）\n" + "\n".join(lines)
    return SystemMessage(content=block)


def _walk_message_chain(
    msg_dict: dict,
    start_id: uuid.UUID | None,
    max_depth: int = 500,
) -> list:
    """Trace parent_id links from start_id, returning messages chronologically."""
    history: list = []
    current_id = start_id
    depth = 0
    while current_id and current_id in msg_dict and depth < max_depth:
        history.append(msg_dict[current_id])
        current_id = msg_dict[current_id].parent_id
        depth += 1
    history.reverse()
    return history


def _build_langchain_messages(history: list) -> list:
    """Convert a sequence of DB Message objects into LangChain message types."""
    lc_messages = []
    for msg in history:
        message_class = _ROLE_TO_MESSAGE.get(msg.role)
        if not message_class:
            logger.debug(
                "chat_history_message_skipped",
                role=msg.role,
                msg_id=str(msg.id),
            )
            continue
        kwargs = _build_message_kwargs(msg)
        lc_messages.append(message_class(**kwargs))
    return lc_messages


def _build_message_kwargs(msg: Message) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"content": msg.content}

    if msg.role == "human" and msg.image_urls:
        content_blocks: list[dict[str, Any]] = [{"type": "text", "text": msg.content}]
        for url in msg.image_urls:
            content_blocks.append({"type": "image_url", "image_url": {"url": url}})
        kwargs["content"] = content_blocks

    if msg.role == "ai" and msg.tool_calls:
        kwargs["tool_calls"] = msg.tool_calls

    if msg.role == "tool":
        kwargs.update(_build_tool_message_kwargs(msg))

    return kwargs


def _build_tool_message_kwargs(msg: Message) -> dict[str, Any]:
    tool_payload: dict[str, Any] | None = None
    try:
        parsed = json.loads(msg.content)
        if isinstance(parsed, dict):
            tool_payload = parsed
    except json.JSONDecodeError:
        tool_payload = None

    if not tool_payload:
        return {"tool_call_id": str(msg.id)}

    kwargs: dict[str, Any] = {
        "content": str(tool_payload.get("content", msg.content)),
        "tool_call_id": str(tool_payload.get("tool_call_id") or msg.id),
    }
    if tool_payload.get("name"):
        kwargs["name"] = str(tool_payload["name"])
    return kwargs


def _tool_call_signature(tool_calls: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(
        str(tc.get("id") or f"{tc.get('name', 'tool')}_{idx}")
        for idx, tc in enumerate(tool_calls)
    )


def _serialize_tool_message(tool_msg: ToolMessage) -> str:
    return json.dumps(
        {
            "tool_call_id": getattr(tool_msg, "tool_call_id", None),
            "name": tool_msg.name,
            "content": tool_msg.content,
        }
    )


def _extract_token_counts(ai_msg: object | None) -> tuple[int, int]:
    """Return (tokens_in, tokens_out) from an AIMessage's usage_metadata."""
    if ai_msg is None:
        return 0, 0
    meta = getattr(ai_msg, "usage_metadata", None)
    if not meta:
        return 0, 0
    return meta.get("input_tokens", 0) or 0, meta.get("output_tokens", 0) or 0
```

- [ ] **Step 5: Create graph_builder.py**

```python
# backend/app/api/chat/graph_builder.py
"""Expert agent graph selection — maps routing label to compiled LangGraph."""

from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import create_graph


def _build_expert_graph(
    route: str,
    *,
    provider: str,
    model: str,
    api_key: str,
    api_keys: list[str] | None,
    user_id: str,
    openai_api_key: str | None,
    tavily_api_key: str | None,
    enabled_tools: list[str] | None,
    mcp_tools: list,
    plugin_tools: list | None,
    conversation_id: str,
    base_url: str | None = None,
    workflow_dsl: dict | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> CompiledStateGraph:
    """Return the appropriate compiled LangGraph for the given routing label.

    Expert agents (code/research/writing) each select a focused tool subset.
    Workflow DSLs take precedence over default agents.
    Unknown labels fall back to the standard ReAct graph with all enabled tools.
    """
    if workflow_dsl:
        from app.agent.compiler import GraphCompiler, WorkflowDSL

        compiler = GraphCompiler(
            dsl=WorkflowDSL(**workflow_dsl),
            llm_config={
                "provider": provider,
                "api_key": api_key,
                "base_url": base_url,
                "temperature": temperature,
                **({"max_tokens": max_tokens} if max_tokens else {}),
            },
        )
        return compiler.compile()

    from app.agent.experts import (
        create_code_agent_graph,
        create_research_agent_graph,
        create_writing_agent_graph,
    )

    if route == "code":
        return create_code_agent_graph(
            provider=provider,
            model=model,
            api_key=api_key,
            user_id=user_id,
            openai_api_key=openai_api_key,
            api_keys=api_keys,
            mcp_tools=mcp_tools,
            plugin_tools=plugin_tools,
            conversation_id=conversation_id,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if route == "research":
        return create_research_agent_graph(
            provider=provider,
            model=model,
            api_key=api_key,
            user_id=user_id,
            openai_api_key=openai_api_key,
            tavily_api_key=tavily_api_key,
            api_keys=api_keys,
            mcp_tools=mcp_tools,
            plugin_tools=plugin_tools,
            conversation_id=conversation_id,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if route == "writing":
        return create_writing_agent_graph(
            provider=provider,
            model=model,
            api_key=api_key,
            user_id=user_id,
            openai_api_key=openai_api_key,
            api_keys=api_keys,
            mcp_tools=mcp_tools,
            plugin_tools=plugin_tools,
            conversation_id=conversation_id,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    return create_graph(
        provider=provider,
        model=model,
        api_key=api_key,
        enabled_tools=enabled_tools,
        api_keys=api_keys,
        user_id=user_id,
        openai_api_key=openai_api_key,
        tavily_api_key=tavily_api_key,
        mcp_tools=mcp_tools,
        plugin_tools=plugin_tools,
        conversation_id=conversation_id,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )
```

- [ ] **Step 6: Create tool_loader.py**

```python
# backend/app/api/chat/tool_loader.py
"""Tool loading helpers — loads MCP, plugin, and personal plugin tools per request."""

import structlog
from langchain_core.tools import BaseTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import InstalledPlugin
from app.plugins import plugin_registry

logger = structlog.get_logger(__name__)


async def _load_personal_plugin_tools(
    user_id: str, db: AsyncSession
) -> list[BaseTool]:
    """Load personal installed skill_md/python_plugin tools for this request."""
    try:
        from app.plugins.loader import _load_from_directory, load_markdown_skills
        from app.plugins.registry import PluginRegistry

        result = await db.execute(
            select(InstalledPlugin).where(
                InstalledPlugin.scope == "personal",
                InstalledPlugin.installed_by == user_id,
                InstalledPlugin.type.in_(["skill_md", "python_plugin"]),
            )
        )
        rows = result.scalars().all()
        if not rows:
            return []

        from pathlib import Path

        personal_dir = Path(settings.installed_plugins_dir) / "users" / str(user_id)
        if not personal_dir.exists():
            return []

        personal_registry = PluginRegistry()
        _load_from_directory(personal_registry, personal_dir)
        await load_markdown_skills(personal_registry, [personal_dir])
        return personal_registry.get_all_tools()
    except Exception:
        logger.exception("personal_plugin_load_failed", user_id=user_id)
        return []


async def _load_tools(enabled_tools: list[str] | None) -> tuple[list, list | None]:
    """Load MCP and plugin tools based on the user's enabled_tools config."""
    mcp_tools: list = []
    if enabled_tools is None or "mcp" in enabled_tools:
        from app.tools.mcp_client import create_mcp_tools, parse_mcp_configs

        mcp_tools = await create_mcp_tools(parse_mcp_configs(settings.mcp_servers_json))

    plugin_tools: list | None = None
    if enabled_tools is None or "plugin" in enabled_tools:
        plugin_tools = plugin_registry.get_all_tools() or None

    return mcp_tools, plugin_tools
```

**Note:** `_load_personal_plugin_tools` in the original chat.py used the request-level `db` session implicitly (via closure). The refactored version takes `db` as an explicit parameter. Update the call site in `routes.py` accordingly.

- [ ] **Step 7: Create routes.py**

This file contains `router`, `chat_stream`, and `chat_regenerate`. Copy the two route handler functions from `chat.py` (lines 449–926 and 936–1223), updating internal function calls to import from the new sub-modules.

Key imports at the top of routes.py:
```python
# backend/app/api/chat/routes.py
import asyncio
import uuid
from collections.abc import AsyncGenerator
from dataclasses import replace as dc_replace
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, SystemMessage
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.compressor import compact_messages
from app.agent.persona import build_system_prompt
from app.agent.router import classify_task
from app.agent.state import AgentState
from app.agent.supervisor import SupervisorState, create_supervisor_graph
from app.api.chat.graph_builder import _build_expert_graph
from app.api.chat.message_builder import (
    _build_langchain_messages,
    _build_memory_message,
    _extract_token_counts,
    _serialize_tool_message,
    _tool_call_signature,
    _walk_message_chain,
)
from app.api.chat.schemas import ChatRequest, RegenerateRequest
from app.api.chat.sse import _format_sse, _sse_events_from_chunk
from app.api.chat.tool_loader import _load_personal_plugin_tools, _load_tools
from app.api.deps import get_current_user, get_llm_config
from app.api.settings import PROVIDER_MODELS
from app.core.config import settings
from app.core.limiter import limiter
from app.core.metrics import llm_requests_total
from app.core.sanitizer import sanitize_user_input
from app.core.security import resolve_api_key
from app.db.models import AgentSession, Conversation, InstalledPlugin, Message, User, UserMemory
from app.db.session import AsyncSessionLocal, get_db
from app.plugins import plugin_registry
from app.rag.context import build_rag_context
from app.services.memory_sync import sync_conversation_to_markdown

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])
```

Then paste the full `chat_stream` and `chat_regenerate` function bodies verbatim, replacing only the calls that changed:
- `_load_personal_plugin_tools(user_id)` → `_load_personal_plugin_tools(user_id, db)` (pass the db session explicitly)

- [ ] **Step 8: Create __init__.py**

Re-export everything that tests and main.py depend on:

```python
# backend/app/api/chat/__init__.py
"""Chat API package — streaming conversation endpoints."""

from app.api.chat.graph_builder import _build_expert_graph
from app.api.chat.message_builder import _build_langchain_messages
from app.api.chat.routes import chat_regenerate, chat_stream, router
from app.api.chat.schemas import ChatRequest, RegenerateRequest
from app.api.chat.sse import _format_sse, _sse_events_from_chunk
from app.api.chat.tool_loader import _load_tools

__all__ = [
    "router",
    "chat_stream",
    "chat_regenerate",
    "ChatRequest",
    "RegenerateRequest",
    "_build_expert_graph",
    "_build_langchain_messages",
    "_format_sse",
    "_sse_events_from_chunk",
    "_load_tools",
]
```

- [ ] **Step 9: Delete original chat.py**

```bash
cd backend
rm app/api/chat.py
```

- [ ] **Step 10: Run import check**

```bash
cd backend
uv run pytest --collect-only -q 2>&1 | tail -10
```

Expected: no import errors.

- [ ] **Step 11: Run chat tests**

```bash
cd backend
uv run pytest tests/api/test_chat.py tests/api/test_chat_routing.py \
              tests/api/test_ollama_stream.py tests/tools/test_chat_sse_tools.py -v
```

Expected: all pass.

- [ ] **Step 12: Commit**

```bash
git add backend/app/api/chat/ backend/app/api/chat.py
git commit -m "refactor: split api/chat.py into focused submodules (schemas/sse/message_builder/graph_builder/tool_loader/routes)"
```

---

## Task 6: Document the tools↔agent circular import mitigation

**Context:** `tools/subagent_tool.py` and `agent/graph.py` have a mutually recursive dependency — graph imports tools, and subagent_tool needs graph to spawn sub-agents. This is intentionally broken at module load time using delayed (runtime) imports inside function bodies. The pattern is correct; the documentation should make the architecture decision explicit.

**Files:**
- Modify: `backend/app/tools/subagent_tool.py` (improve module docstring)
- Modify: `backend/app/agent/graph.py` (add comment at delayed import site)

- [ ] **Step 1: Update subagent_tool.py module docstring**

At the top of the file, replace or add a module docstring:

```python
"""Subagent tool — spawns a nested agent graph to handle a subtask.

Architecture note — delayed imports:
    This module and app.agent.graph are mutually dependent:
      graph.py → (resolves tools) → subagent_tool.py → (at call time) → graph.py

    Both dependencies are broken at module-load time using function-body imports:
      - graph.py imports create_subagent_tool *inside* _resolve_tools() (called at runtime)
      - this module imports create_graph *inside* spawn_subagent() (called at runtime)

    Do not move either import to module level — it will cause a circular ImportError.
"""
```

- [ ] **Step 2: Reinforce the comment at the delayed import site in subagent_tool.py**

Find the delayed import block (around line 55) and update the comment:

```python
# Delayed import — breaks the graph → tools → graph circular dependency.
# See module docstring for the full explanation.
from app.agent.graph import create_graph
from app.agent.state import AgentState
```

- [ ] **Step 3: Update agent/graph.py comment at delayed import site**

Find the import of `create_subagent_tool` inside `_resolve_tools()` and update its comment:

```python
# Delayed import — breaks the graph → tools → graph circular dependency.
# subagent_tool.py also imports create_graph at call time (not module load time).
from app.tools.subagent_tool import create_subagent_tool
```

- [ ] **Step 4: Run import check**

```bash
cd backend
uv run pytest --collect-only -q 2>&1 | tail -5
```

Expected: no import errors.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tools/subagent_tool.py backend/app/agent/graph.py
git commit -m "docs: document delayed-import pattern that breaks tools/agent circular dependency"
```

---

## Task 7: Fix exception handling in critical API paths

**Scope:** Fix `except Exception:` usage in API routes where it silently swallows errors or should catch specific types. Do NOT change exception handling in:
- `core/audit.py` / `services/audit.py` — intentional broad catch (must never break request path)
- SSE generators in `chat.py` / `chat/routes.py` — intentional broad catch (prevent stream termination)
- Channel adapters — intentional broad catch (one channel must not crash others)
- Tool implementations — intentional broad catch (tool errors reported back to LLM)

**Target files:**
- `backend/app/api/documents.py` — 5 bare except Exception: cases
- `backend/app/api/voice.py` — 5 bare except Exception: cases
- `backend/app/api/canvas.py` — 1 bare except Exception: case
- `backend/app/api/settings.py` — 1 bare except Exception: case
- `backend/app/api/workflows.py` — 1 bare except Exception: case

**Pattern to apply:**

Every `except Exception:` in an API endpoint that does NOT have a logger call afterward should add one. Cases where the exception IS already logged can remain broad. Cases where a more specific exception type makes sense should be narrowed.

- [ ] **Step 1: Fix documents.py**

Read `api/documents.py` lines around 194, 221, 304, 309, 449, 452.

For Qdrant/MinIO operations (infrastructure calls), the correct pattern is:
```python
# Before
except Exception:
    logger.exception("qdrant_delete_failed", doc_id=str(doc.id))

# This is already correct — broad catch is appropriate for infrastructure failures.
# Keep as-is when logger.exception is called.
```

For cases where `except Exception:` is followed by only a return or raise, check if a more specific type is appropriate:
```python
# If the code is catching a file I/O error:
except OSError:
    logger.exception("file_operation_failed")
    raise HTTPException(status_code=500)

# If catching SQLAlchemy integrity errors:
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
except IntegrityError:
    raise HTTPException(status_code=409, detail="Conflict")
except SQLAlchemyError:
    logger.exception("db_operation_failed")
    raise HTTPException(status_code=500)
```

Read each case in context and apply the narrowest correct exception type that still handles all real failure modes.

- [ ] **Step 2: Fix voice.py**

Read `api/voice.py` lines around 192, 204, 240, 246, 286.

TTS/STT operations can fail with various errors (HTTP errors, I/O errors). Where the exception is already logged with `logger.exception`, keep broad. Where it's not logged, add logging:
```python
except Exception:
    logger.exception("tts_generation_failed")
    raise HTTPException(status_code=502, detail="TTS service error")
```

- [ ] **Step 3: Fix canvas.py line ~74**

Read the context. If this is an infrastructure call, ensure it logs:
```python
except Exception:
    logger.exception("canvas_render_failed")
    raise HTTPException(status_code=500)
```

- [ ] **Step 4: Fix settings.py line ~104**

Read context. Apply appropriate specific exception or add logging.

- [ ] **Step 5: Fix workflows.py line ~353**

Read context and apply narrowest appropriate handler.

- [ ] **Step 6: Run lint check**

```bash
cd backend
uv run ruff check app/api/documents.py app/api/voice.py app/api/canvas.py \
                  app/api/settings.py app/api/workflows.py
```

Expected: no new errors.

- [ ] **Step 7: Run affected tests**

```bash
cd backend
uv run pytest tests/api/ -v -k "document or voice or canvas or workflow"
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/documents.py backend/app/api/voice.py \
        backend/app/api/canvas.py backend/app/api/settings.py \
        backend/app/api/workflows.py
git commit -m "fix: improve exception handling in API routes — add logging where missing, narrow types where appropriate"
```

---

## Final Verification

- [ ] **Run full backend static checks**

```bash
cd backend
uv run ruff check --fix && uv run ruff format
uv run mypy app
```

Expected: no errors.

- [ ] **Run full test suite**

```bash
cd backend
uv run pytest tests/ -x -q --tb=short
```

Expected: all pass (or same pass rate as before — no regressions).

- [ ] **Run pytest collection (catches import errors)**

```bash
cd backend
uv run pytest --collect-only -q 2>&1 | tail -10
```

Expected: no import errors, all tests collected.
