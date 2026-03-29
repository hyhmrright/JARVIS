# P5: Domain Model Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move business logic from the API layer (840-line `conversations.py`, `workflows.py`) into the domain model classes (`Conversation`, `Message`, `Workflow`, `WorkflowRun`), eliminating the anemic domain model. Executed in three separate PRs to contain risk.

**Architecture:** Add factory class methods (`Conversation.create()`) and state-mutating methods (`conversation.activate_leaf()`) to SQLAlchemy model classes. These methods are pure Python — no session dependency. The API layer calls these methods instead of constructing model instances inline. No DB schema changes (no new migrations needed).

**Tech Stack:** Python dataclasses/methods, SQLAlchemy ORM models, pytest

**Prerequisite:** P1 must be merged (provides clean service layer boundary to compare against).

---

## Batch 1: `Conversation` and `Message` factory methods

### Task 1: Add factory methods to `Conversation` model

**Files:**
- Modify: `backend/app/db/models/conversation.py`
- Test: `backend/tests/db/test_conversation_model.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/db/test_conversation_model.py
"""Unit tests for Conversation domain methods — no DB connection needed."""

import uuid
import pytest
from app.db.models import Conversation, Message


def test_conversation_create_sets_required_fields():
    """Conversation.create() must set user_id and title."""
    user_id = uuid.uuid4()
    conv = Conversation.create(user_id=user_id, title="My Chat")
    assert conv.user_id == user_id
    assert conv.title == "My Chat"
    assert conv.id is not None


def test_conversation_create_default_title():
    """Conversation.create() without title must use 'New Conversation'."""
    conv = Conversation.create(user_id=uuid.uuid4())
    assert conv.title == "New Conversation"


def test_conversation_activate_leaf_sets_id():
    """activate_leaf() must update active_leaf_id."""
    conv = Conversation.create(user_id=uuid.uuid4())
    msg_id = uuid.uuid4()
    conv.activate_leaf(msg_id)
    assert conv.active_leaf_id == msg_id


def test_conversation_update_title():
    """update_title() must change the title."""
    conv = Conversation.create(user_id=uuid.uuid4(), title="Old")
    conv.update_title("New Title")
    assert conv.title == "New Title"


def test_message_create_sets_role_and_content():
    """Message.create() must set role, content, and conversation_id."""
    conv_id = uuid.uuid4()
    msg = Message.create(conversation_id=conv_id, role="human", content="hello")
    assert msg.role == "human"
    assert msg.content == "hello"
    assert msg.conversation_id == conv_id
    assert msg.id is not None


def test_message_create_with_parent():
    """Message.create() with parent_id must store the parent link."""
    conv_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    msg = Message.create(
        conversation_id=conv_id,
        role="ai",
        content="reply",
        parent_id=parent_id,
    )
    assert msg.parent_id == parent_id
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/db/test_conversation_model.py -v
```
Expected: `AttributeError` — methods don't exist yet.

- [ ] **Step 3: Add methods to `Conversation` and `Message`**

Open `backend/app/db/models/conversation.py`. Find the `Conversation` class and add these methods **inside** the class body, after the column definitions:

```python
# Inside class Conversation(Base):

@classmethod
def create(
    cls,
    user_id: uuid.UUID,
    title: str = "New Conversation",
) -> "Conversation":
    """Factory: create a Conversation instance with required fields set.

    Does not add to a session — the caller must call ``db.add(conv)``.
    """
    return cls(id=uuid.uuid4(), user_id=user_id, title=title)

def activate_leaf(self, message_id: uuid.UUID) -> None:
    """Set the active leaf message for this conversation."""
    self.active_leaf_id = message_id

def update_title(self, new_title: str) -> None:
    """Update the conversation title."""
    self.title = new_title
```

Find the `Message` class and add:

```python
# Inside class Message(Base):

@classmethod
def create(
    cls,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    parent_id: uuid.UUID | None = None,
    image_urls: list | None = None,
    tool_calls: list | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
    tokens_input: int | None = None,
    tokens_output: int | None = None,
) -> "Message":
    """Factory: create a Message instance.

    Does not add to a session — the caller must call ``db.add(msg)``.
    """
    return cls(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        parent_id=parent_id,
        image_urls=image_urls,
        tool_calls=tool_calls,
        model_provider=model_provider,
        model_name=model_name,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
    )
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/db/test_conversation_model.py -v
```
Expected: all 6 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/db/models/conversation.py tests/db/test_conversation_model.py
git commit -m "feat: add Conversation.create(), activate_leaf(), Message.create() factory methods"
```

---

### Task 2: Migrate `api/conversations.py` to use domain methods (Batch 1 API migration)

**Files:**
- Modify: `backend/app/api/conversations.py`

- [ ] **Step 1: Replace inline `Conversation(...)` construction**

Search for all occurrences of `Conversation(` in `app/api/conversations.py`.

Before (example):
```python
conv = Conversation(
    user_id=user.id,
    title=body.title or "New Conversation",
)
db.add(conv)
```

After:
```python
conv = Conversation.create(user_id=user.id, title=body.title or "New Conversation")
db.add(conv)
```

- [ ] **Step 2: Replace inline `Message(...)` construction for human messages**

Before:
```python
msg = Message(
    conversation_id=conv.id,
    role="human",
    content=body.content,
    parent_id=parent_id,
)
db.add(msg)
```

After:
```python
msg = Message.create(
    conversation_id=conv.id,
    role="human",
    content=body.content,
    parent_id=parent_id,
)
db.add(msg)
```

- [ ] **Step 3: Replace direct `conv.active_leaf_id = ...` with `conv.activate_leaf(...)`**

Before:
```python
conv.active_leaf_id = ai_msg_id
```

After:
```python
conv.activate_leaf(ai_msg_id)
```

- [ ] **Step 4: Run existing conversations tests**

```bash
cd backend && uv run pytest tests/api/test_conversations.py -v --tb=short
```
Expected: all pass (behavior unchanged — same SQL queries, just via methods).

- [ ] **Step 5: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/api/conversations.py
git commit -m "refactor: conversations.py uses Conversation.create() and Message.create()"
```

---

## Batch 2: `Workflow` and `WorkflowRun` state machine methods

### Task 3: Add state machine methods to `Workflow` and `WorkflowRun`

**Files:**
- Modify: `backend/app/db/models/misc.py` (where Workflow/WorkflowRun live)
- Test: `backend/tests/db/test_workflow_model.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/db/test_workflow_model.py
import uuid
import pytest
from app.db.models import Workflow, WorkflowRun


def test_workflow_create():
    user_id = uuid.uuid4()
    wf = Workflow.create(user_id=user_id, name="My Flow", dsl={"nodes": []})
    assert wf.user_id == user_id
    assert wf.name == "My Flow"
    assert wf.dsl == {"nodes": []}
    assert wf.id is not None


def test_workflow_run_start():
    wf_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run = WorkflowRun.start(workflow_id=wf_id, user_id=user_id)
    assert run.status == "running"
    assert run.workflow_id == wf_id
    assert run.started_at is not None


def test_workflow_run_complete():
    run = WorkflowRun.start(workflow_id=uuid.uuid4(), user_id=uuid.uuid4())
    run.complete(output="result text")
    assert run.status == "completed"
    assert run.output == "result text"
    assert run.finished_at is not None


def test_workflow_run_fail():
    run = WorkflowRun.start(workflow_id=uuid.uuid4(), user_id=uuid.uuid4())
    run.fail(error="timeout exceeded")
    assert run.status == "failed"
    assert run.error == "timeout exceeded"
    assert run.finished_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/db/test_workflow_model.py -v
```
Expected: `AttributeError`.

- [ ] **Step 3: Add methods to `Workflow` and `WorkflowRun` in `app/db/models/misc.py`**

Inside the `Workflow` class:

```python
@classmethod
def create(
    cls,
    user_id: uuid.UUID,
    name: str,
    dsl: dict,
    description: str | None = None,
) -> "Workflow":
    """Factory: create a Workflow instance. Does not add to session."""
    return cls(id=uuid.uuid4(), user_id=user_id, name=name, dsl=dsl, description=description)
```

Inside the `WorkflowRun` class:

```python
@classmethod
def start(cls, workflow_id: uuid.UUID, user_id: uuid.UUID) -> "WorkflowRun":
    """Create a WorkflowRun in 'running' status."""
    from datetime import UTC, datetime
    return cls(
        id=uuid.uuid4(),
        workflow_id=workflow_id,
        user_id=user_id,
        status="running",
        started_at=datetime.now(UTC),
    )

def complete(self, output: str) -> None:
    """Transition to 'completed' status with output."""
    from datetime import UTC, datetime
    self.status = "completed"
    self.output = output
    self.finished_at = datetime.now(UTC)

def fail(self, error: str) -> None:
    """Transition to 'failed' status with error message."""
    from datetime import UTC, datetime
    self.status = "failed"
    self.error = error
    self.finished_at = datetime.now(UTC)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/db/test_workflow_model.py -v
```
Expected: all 4 tests `PASSED`.

- [ ] **Step 5: Migrate `api/workflows.py`**

Replace `WorkflowRun(status="running", ...)` constructors with `WorkflowRun.start(...)`.
Replace `run.status = "completed"` with `run.complete(output=...)`.
Replace `run.status = "failed"` with `run.fail(error=...)`.

- [ ] **Step 6: Run workflow tests**

```bash
cd backend && uv run pytest tests/api/test_workflows.py -v --tb=short
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/db/models/misc.py app/api/workflows.py tests/db/test_workflow_model.py
git commit -m "feat: add Workflow.create() and WorkflowRun state machine methods"
```

---

## Batch 3: `UserSettings` API key methods

### Task 4: Add encryption methods to `UserSettings` model

**Files:**
- Modify: `backend/app/db/models/user.py`
- Test: `backend/tests/db/test_user_settings_model.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/db/test_user_settings_model.py
import uuid
import pytest
from unittest.mock import MagicMock, patch


def test_user_settings_get_api_key_returns_none_when_missing():
    """get_api_key() must return None when the key for a provider is not set."""
    from app.db.models import UserSettings

    us = UserSettings(user_id=uuid.uuid4(), api_keys={})
    mock_fernet = MagicMock()

    result = us.get_api_key("openai", mock_fernet)
    assert result is None
    mock_fernet.decrypt.assert_not_called()


def test_user_settings_get_api_key_decrypts_stored_key():
    """get_api_key() must decrypt and return the stored key."""
    from app.db.models import UserSettings

    us = UserSettings(user_id=uuid.uuid4(), api_keys={"openai": "encrypted_blob"})
    mock_fernet = MagicMock()
    mock_fernet.decrypt.return_value = b"sk-openai-real"

    result = us.get_api_key("openai", mock_fernet)
    assert result == "sk-openai-real"
    mock_fernet.decrypt.assert_called_once_with(b"encrypted_blob")


def test_user_settings_set_api_key_encrypts_and_stores():
    """set_api_key() must encrypt and store the key in api_keys."""
    from app.db.models import UserSettings

    us = UserSettings(user_id=uuid.uuid4(), api_keys={})
    mock_fernet = MagicMock()
    mock_fernet.encrypt.return_value = b"encrypted_result"

    us.set_api_key("deepseek", "sk-ds-key", mock_fernet)

    assert us.api_keys.get("deepseek") == "encrypted_result"
    mock_fernet.encrypt.assert_called_once_with(b"sk-ds-key")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/db/test_user_settings_model.py -v
```
Expected: `AttributeError`.

- [ ] **Step 3: Add methods to `UserSettings` in `app/db/models/user.py`**

Inside the `UserSettings` class:

```python
def get_api_key(self, provider: str, fernet) -> str | None:
    """Decrypt and return the API key for the given provider.

    Args:
        provider: e.g. 'openai', 'deepseek', 'anthropic'
        fernet: a ``cryptography.fernet.Fernet`` instance for decryption

    Returns:
        Decrypted key string, or None if not set.
    """
    raw = (self.api_keys or {}).get(provider)
    if raw is None:
        return None
    try:
        return fernet.decrypt(raw.encode() if isinstance(raw, str) else raw).decode()
    except Exception:
        return None

def set_api_key(self, provider: str, plaintext_key: str, fernet) -> None:
    """Encrypt and store the API key for the given provider.

    Args:
        provider: e.g. 'openai', 'deepseek', 'anthropic'
        plaintext_key: the unencrypted API key string
        fernet: a ``cryptography.fernet.Fernet`` instance for encryption
    """
    encrypted = fernet.encrypt(
        plaintext_key.encode() if isinstance(plaintext_key, str) else plaintext_key
    )
    if self.api_keys is None:
        self.api_keys = {}
    self.api_keys[provider] = encrypted.decode() if isinstance(encrypted, bytes) else encrypted
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/db/test_user_settings_model.py -v
```
Expected: all 3 tests `PASSED`.

- [ ] **Step 5: Run full test suite**

```bash
cd backend && uv run pytest tests/ -x -q --tb=short
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/db/models/user.py tests/db/test_user_settings_model.py
git commit -m "feat: add UserSettings.get_api_key() and set_api_key() domain methods"
```

---

### Task 5: Final P5 verification

- [ ] **Step 1: Verify no anemic model usage in core paths**

```bash
# Check that conversations.py no longer constructs Conversation() directly
grep -n "Conversation(" backend/app/api/conversations.py | grep -v "\.create(" | grep -v "select\|where\|import\|#"
```
Expected: no matches (all inline constructions replaced with `.create()`).

- [ ] **Step 2: Run full test suite**

```bash
cd backend && uv run pytest tests/ -x -q --tb=short
```
Expected: all pass.

- [ ] **Step 3: Push**

```bash
git push origin dev
```
