# Public Sharing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to generate a public, read-only link for a conversation. This shared view will include the full message history and the final state of the Canvas.

**Architecture:** 
1. Database adds a `shared_conversations` table to store `id` (public token), `conversation_id`, and `created_at`.
2. Backend provides a POST `/conversations/{id}/share` endpoint to create a share entry and a GET `/public/share/{token}` endpoint for unauthenticated access.
3. Frontend adds a "Share" button in the chat header and a new `SharedChatPage.vue` route for the public view.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Vue 3, Vue Router.

---

## Chunk 1: Backend Database & Shared API

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/XXX_add_shared_conversations.py`
- Modify: `backend/app/api/conversations.py`

- [ ] **Step 1: Add SharedConversation Model**
  In `backend/app/db/models.py`, add:
  ```python
  class SharedConversation(Base):
      __tablename__ = "shared_conversations"
      id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
      created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
      
      conversation: Mapped["Conversation"] = relationship()
  ```

- [ ] **Step 2: Generate Migration**
  Run: `cd backend && uv run alembic revision --autogenerate -m "add_shared_conversations"`
  Run: `cd backend && uv run alembic upgrade head`

- [ ] **Step 3: Implement Share Endpoint**
  In `backend/app/api/conversations.py`, add a POST route to create a sharing entry.

- [ ] **Step 4: Implement Public Get Endpoint**
  Create a new file `backend/app/api/public.py` (or add to `conversations.py` if easier, but public needs no auth). 
  Add `router = APIRouter(prefix="/public", tags=["public"])`.
  Implement `GET /public/share/{token}` which returns messages and conversation title.

- [ ] **Step 5: Register Public Router**
  In `backend/app/main.py`, include the new public router.

- [ ] **Step 6: Commit**
  Run: `git add backend/ && git commit -m "feat(backend): implement public sharing API and database schema"`

---

## Chunk 2: Frontend Shared Route & Logic

**Files:**
- Create: `frontend/src/pages/SharedChatPage.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add Shared Route**
  In `frontend/src/router/index.ts`, add a path `/share/:token` mapping to `SharedChatPage.vue`. This route should be marked as `meta: { public: true }`.

- [ ] **Step 2: Implement SharedChatPage.vue**
  This page should fetch data from `/api/public/share/:token`.
  It should reuse the message rendering components from `ChatPage.vue` but remove all inputs, sidebars, and authenticated actions.

- [ ] **Step 3: Update API Client for Public Access**
  Ensure the Axios interceptor doesn't crash if no token is present when accessing `/api/public`.

- [ ] **Step 4: Commit**
  Run: `git add frontend/ && git commit -m "feat(frontend): add shared chat page and route"`

---

## Chunk 3: Share UI & Polish

**Files:**
- Modify: `frontend/src/pages/ChatPage.vue`

- [ ] **Step 1: Add Share Button**
  In the `ChatPage.vue` header, find the `Share2` icon button. Implement a click handler that calls the share API.

- [ ] **Step 2: Show Share URL Modal**
  When shared, show a small overlay or toast with the full URL and a "Copy" button.

- [ ] **Step 3: Final Checks & Push**
  Run: `cd frontend && bun run type-check && bun run lint:fix`
  Run: `cd backend && uv run pytest tests/`
  Run: `git add frontend/src/pages/ChatPage.vue && git commit -m "feat(frontend): add share button and copy link UI"`
  Run: `git push origin HEAD`
