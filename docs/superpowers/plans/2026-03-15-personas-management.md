# Personas Management Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to create and save custom Agent Personas (System Prompts). Users can select these personas when starting a new conversation.

**Architecture:** 
1. New `Persona` table in the database linked to `User` or `Workspace`.
2. Backend provides CRUD API for Personas.
3. Chat API is updated to optionally accept a `persona_id` which populates `persona_override`.
4. Frontend UI allows creating/managing personas and selecting one in the chat interface.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Vue 3.

---

## Chunk 1: Database & API

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/XXX_add_personas.py`
- Create: `backend/app/api/personas.py`

- [ ] **Step 1: Add Persona Model**
  In `backend/app/db/models.py`, add `Persona` model: `id`, `user_id`, `name`, `description`, `system_prompt`, `created_at`.

- [ ] **Step 2: Generate Migration**
  Run: `cd backend && uv run alembic revision --autogenerate -m "add_personas"`
  Run: `cd backend && uv run alembic upgrade head`

- [ ] **Step 3: Implement Personas CRUD API**
  Create `backend/app/api/personas.py`. Implement GET (list), POST (create), DELETE (delete).

- [ ] **Step 4: Update ChatRequest & logic**
  In `backend/app/api/chat.py`, update `ChatRequest` to include `persona_id`.
  In `chat_stream`, if `persona_id` is provided and the conversation is new, fetch the persona's system prompt and save it to `conv.persona_override`.

- [ ] **Step 5: Register Persona Router**
  In `backend/app/main.py`, include `personas_router`.

- [ ] **Step 6: Commit**
  Run: `git add backend/ && git commit -m "feat(backend): implement personas database and CRUD API"`

---

## Chunk 2: Frontend Persona Management

**Files:**
- Create: `frontend/src/pages/PersonasPage.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/pages/ChatPage.vue`

- [ ] **Step 1: Add Personas Route**
  In `frontend/src/router/index.ts`, add `/personas`.

- [ ] **Step 2: Implement Personas Management UI**
  In `PersonasPage.vue`, allow users to list, create, and delete personas.

- [ ] **Step 3: Integrate Persona Selection in Chat**
  In `ChatPage.vue`, add a dropdown or selector to choose a persona before starting a conversation.

- [ ] **Step 4: Final Checks & Push**
  Run: `cd frontend && bun run type-check && bun run lint:fix`
  Run: `git add frontend/ && git commit -m "feat(frontend): implement persona management and selection"`
  Run: `git push origin HEAD`
