# Chat Branching & WebSocket Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the chat experience by introducing tree-based conversation branching (support for regenerating replies and navigating versions) and robust dual-channel (WebSocket + SSE fallback) real-time communication.

**Architecture:** 
1. The `Message` model will gain a `parent_id` (self-referencing FK) to turn the linear conversation history into a tree. 
2. The `POST /api/chat/stream` and new `POST /api/chat/regenerate` endpoints will construct histories by traversing up the parent pointers. 
3. A new `WebSocket` endpoint will provide bi-directional messaging, falling back to SSE if WebSockets fail. 
4. The Vue frontend will be updated to display version switching controls (e.g. `1/3`) on messages.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Alembic, Vue 3, Pinia.

---

## Chunk 1: Database & Schema Evolution

### Task 1: Update Message Model and Migrate Database

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/<revision>_add_message_parent_id.py` (via alembic command)
- Test: `backend/tests/db/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# In backend/tests/db/test_models.py (add or create)
import pytest
from app.db.models import Message

@pytest.mark.asyncio
async def test_message_parent_id_relationship(db_session, user_factory, conversation_factory):
    user = await user_factory()
    conv = await conversation_factory(user_id=user.id)
    
    parent_msg = Message(conversation_id=conv.id, role="human", content="Hello")
    db_session.add(parent_msg)
    await db_session.commit()
    
    child_msg = Message(conversation_id=conv.id, role="ai", content="Hi", parent_id=parent_msg.id)
    db_session.add(child_msg)
    await db_session.commit()
    
    assert child_msg.parent_id == parent_msg.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/db/test_models.py -v`
Expected: FAIL (AttributeError: 'Message' has no attribute 'parent_id' or similar)

- [ ] **Step 3: Write minimal implementation**

```python
# In backend/app/db/models.py
# Inside class Message(Base):
parent_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("messages.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)
```

- [ ] **Step 4: Generate Alembic migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add message parent_id"
```
*Note: Ensure the generated script correctly adds the column to the `messages` table.*

- [ ] **Step 5: Apply migration and run test**

Run: `cd backend && uv run alembic upgrade head`
Run: `cd backend && uv run pytest tests/db/test_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models.py backend/alembic/versions/ backend/tests/db/
git commit -m "feat: add parent_id to Message model for branching"
```

---

## Chunk 2: Backend Core API

### Task 2: Update Chat Endpoint to Handle parent_id

**Files:**
- Modify: `backend/app/api/chat.py`
- Modify: `backend/tests/api/test_chat.py`

- [ ] **Step 1: Write the failing test**

```python
# In backend/tests/api/test_chat.py (add to existing test_chat_stream)
@pytest.mark.asyncio
async def test_chat_stream_sets_parent_id(async_client, user_auth_headers, test_db):
    # Setup conversation
    # Post to /api/chat/stream
    # Verify the created human message has parent_id set to the previous AI message
    # Verify the created AI message has parent_id set to the human message
    pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_chat.py -k test_chat_stream_sets_parent_id -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api/chat.py`:
- Modify `POST /api/chat/stream` to accept an optional `parent_message_id` in the request body.
- When saving the `human` message, set its `parent_id` to the provided `parent_message_id` (or the last message in the conversation if null).
- Pass this `human` message ID to the background generator.
- When saving the final `ai` message in the generator, set its `parent_id` to the `human` message ID.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_chat.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/chat.py backend/tests/api/test_chat.py
git commit -m "feat: chat stream records parent_id correctly"
```

### Task 3: Implement Regenerate Endpoint

**Files:**
- Modify: `backend/app/api/chat.py`
- Modify: `backend/tests/api/test_chat.py`

- [ ] **Step 1: Write the failing test**

```python
# In backend/tests/api/test_chat.py
@pytest.mark.asyncio
async def test_chat_regenerate(async_client, user_auth_headers, test_db):
    # Post to /api/chat/regenerate with a valid message_id
    # Assert it returns a 200 StreamingResponse
    pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_chat.py -k test_chat_regenerate -v`
Expected: FAIL (404 Not Found)

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api/chat.py`:
- Create `POST /api/chat/regenerate`.
- Accepts `{ conversation_id, message_id }`.
- Fetches the original message. Checks its `parent_id`.
- Re-constructs history up to that `parent_id`.
- Triggers the same generator used by stream, but skips creating a new human message, only generating the new AI message (with `parent_id` = original's `parent_id`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_chat.py -k test_chat_regenerate -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/chat.py backend/tests/api/test_chat.py
git commit -m "feat: add /api/chat/regenerate endpoint"
```

---

## Chunk 3: WebSocket Support

### Task 4: Implement WebSocket Chat Endpoint

**Files:**
- Modify: `backend/app/api/chat.py`
- Modify: `backend/tests/api/test_chat.py`

- [ ] **Step 1: Write the failing test**

```python
# In backend/tests/api/test_chat.py
from fastapi.testclient import TestClient
from app.main import app

def test_websocket_chat():
    client = TestClient(app)
    with client.websocket_connect("/api/chat/ws?token=test_token") as websocket:
        websocket.send_json({"type": "chat", "content": "Hello"})
        data = websocket.receive_json()
        assert data["type"] == "token"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_chat.py -k test_websocket_chat -v`
Expected: FAIL (404 / connection rejected)

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api/chat.py`:
- Add `WebSocket` route `/api/chat/ws`.
- Authenticate via query param `token`.
- Wait for incoming JSON `{"conversation_id": "...", "content": "..."}`.
- Trigger agent logic, `await websocket.send_json()` for chunks instead of yielding SSE.
- Support a `"type": "cancel"` message to abort generation.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_chat.py -k test_websocket_chat -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/chat.py backend/tests/api/test_chat.py
git commit -m "feat: add websocket endpoint for chat"
```

---

## Chunk 4: Frontend State & UI

### Task 5: Update Frontend State (Pinia)

**Files:**
- Modify: `frontend/src/stores/chat.ts`

- [ ] **Step 1: Modify Store State**

In `frontend/src/stores/chat.ts`:
- Update `Message` interface to include `parent_id?: string`.
- Update `activeMessages` getter to traverse the tree (start from the latest leaf node and follow `parent_id` up to build the linear thread to display).
- Add an action `switchBranch(messageId: string)` to change the currently viewed leaf node.

- [ ] **Step 2: Verify TypeScript compilation**

Run: `cd frontend && bun run type-check`
Expected: PASS (fix any type errors)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/stores/chat.ts
git commit -m "feat(ui): update chat store to support message trees"
```

### Task 6: UI Version Navigator & Regenerate Button

**Files:**
- Modify: `frontend/src/pages/ChatPage.vue`

- [ ] **Step 1: Implement UI logic**

In `frontend/src/pages/ChatPage.vue`:
- If a message has siblings (same `parent_id`), display `← 1/N →` controls.
- Add a "Regenerate" icon button to AI messages. Clicking it calls `chatStore.regenerate(msg.id)`.

- [ ] **Step 2: Implement WebSocket Client Fallback**

In `frontend/src/pages/ChatPage.vue` or `chat.ts`:
- Try connecting to `ws://${location.host}/api/chat/ws?token=...`.
- If WebSocket connects, use it to send and receive.
- If WebSocket fails, fallback to existing `fetch` SSE logic.

- [ ] **Step 3: Lint and Check**

Run: `cd frontend && bun run lint && bun run type-check`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ChatPage.vue frontend/src/stores/chat.ts
git commit -m "feat(ui): add branching controls and websocket support"
```
