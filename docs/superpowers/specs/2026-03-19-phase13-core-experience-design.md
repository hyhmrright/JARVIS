# Phase 13: Core Experience Enhancement — Design Spec

**Version:** 1.0
**Date:** 2026-03-19
**Status:** Approved for Implementation

## Goal

Close the most impactful UX gaps between JARVIS and top-tier open-source AI platforms
(Open WebUI, Dify, LobeChat) by delivering six self-contained features in a single phase.

---

## Feature 1: Conversation Search & Export

### Problem
Users accumulate hundreds of conversations with no way to find content or save it.

### Design

**Backend — `GET /api/conversations/search`**
- Query param: `q` (required, min 2 chars, 400 if shorter), `limit` (default 20, max 50)
- Search strategy: `ILIKE '%q%'` on `conversations.title` UNION with messages content
  search (`Message.content ILIKE '%q%'`, role IN ('human', 'ai'))
- Returns: `SearchResult` list — `{ conv_id, title, snippet, updated_at }`
- Snippet: first matching message content truncated to 200 chars, highlight match

**Backend — `GET /api/conversations/{id}/export`**
- Query param: `format` (default `md`, accepts `md | json | txt`)
- Authorization: `get_current_user` (normal auth), OR anonymous with `?token=<share_token>`
  (same pattern as `GET /api/public/conversations/{share_id}` — look up `SharedConversation`
  by `share_token`; verify the record exists; then load the conversation).
  Note: `SharedConversation` has no `is_active` field — just check record existence.
  Returns 404 if token invalid or conversation not found.
- `md`: `# Title\n\n**Human:** ...\n\n**Assistant:** ...\n` for each message
- `json`: full conversation object with messages array
- `txt`: plain text, role prefix only
- Returns: `Response` with appropriate Content-Type and Content-Disposition header

**Frontend**
- Sidebar: search icon button → inline search bar (replaces conversation list header)
- Debounced 300ms API call on input, min 2 chars
- Results shown in sidebar list (replace conversation list while searching)
- Clear button returns to normal list
- Export: three-dot menu on conversation → "Export as..." → modal with format selector
- Download triggered via `<a href download>` with blob URL

### DB changes
New Alembic migration adds a `pg_trgm` GIN index on `messages.content` for efficient
substring search. Without this, `ILIKE '%q%'` is a full-table scan.

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ix_messages_content_trgm ON messages USING GIN (content gin_trgm_ops);
```

Migration also adds a GIN trigram index on `conversations.title` for title search.

---

## Feature 2: Multimodal Image Input

### Problem
Image support is wired in the backend (DB column `image_urls`, LangChain content blocks)
but the frontend has no upload UI.

### Design

**Frontend only** — no backend changes needed.

- Chat input: paperclip icon button opens file picker (accept: `image/*`)
- Paste from clipboard also captured (`paste` event on textarea)
- Images converted to `data:` URLs (base64) client-side via `FileReader`
- Size limit: 4 MB per image, max 4 images per message (enforced in UI with toast error)
- Backend validation (new code — does not currently exist): add a Pydantic `@field_validator`
  on `ChatRequest.image_urls` in `chat.py`:
  - Reject if `len(image_urls) > 4` → HTTP 422
  - Reject if any URL string length > 5_600_000 chars (≈4 MB base64) → HTTP 422
- Preview strip above input: thumbnails with × remove button
- On send: `image_urls` populated in the chat request body (existing field)
- Models without vision silently send without images (backend already handles this gracefully)
- Images shown in chat bubbles (already implemented at `msg.image_urls`)

**Security**: base64 data URLs sent in request body, stored in DB `image_urls` JSONB column.
No new file upload endpoint needed.

---

## Feature 3: RAG Source Citations

### Problem
RAG tool results embed citations as plain text in AI response. Users cannot distinguish
retrieved snippets from generated content.

### Design

**Approach: Structured tool message parsing**

The `rag_search` tool already formats output as:
```
[1] Document: "file.pdf" (relevance: 0.87)
<content>
```

**Backend changes:**
- `MessageOut` schema: add `tool_calls: dict | None = None` field
- This field is already stored in DB (`messages.tool_calls` JSONB); just add it to schema
- Note: `tool` role message `content` is already returned by the current API (no change
  needed there). The `tool_calls` field is on `ai` role messages only (LangChain stores
  tool invocation metadata there).

**Frontend changes:**
- After AI message, check `tool_calls` field for entries where function name is `rag_search`
- LangChain serializes `tool_calls` as: `[{"name": "rag_search", "id": "...", "args": {...}}]`
- For each `rag_search` invocation ID, find the sibling `tool` role message whose content
  contains the formatted RAG results (already available in the messages list)
- Parse the structured `[N] Document: "..."` format from that tool message's `content`
- Render as collapsible "Sources" panel below the AI response:
  - Each source: document name + relevance score as % + truncated snippet (150 chars)
  - Collapsed by default, "N sources" toggle button
- If `tool_calls` is null or no `rag_search` entries, render nothing (graceful fallback)

**No streaming changes needed** — tool messages are persisted before AI response streams.

---

## Feature 4: Knowledge Base URL Ingestion

### Problem
Users can only upload files; they cannot add web content to their knowledge base.

### Design

**Backend — `POST /api/documents/ingest-url`**
- Body: `{ url: str, workspace_id?: UUID }`
- Validates URL with `is_safe_url()` from `app.tools.web_fetch_tool` (SSRF protection)
- Fetches page directly with `httpx.AsyncClient` (NOT `web_fetch_tool.web_fetch()` which
  truncates at 8000 chars — we need full content for RAG indexing)
  Parameters: `follow_redirects=True`, `timeout=15s`; abort if `Content-Length > 5MB`
- Extracts text with BeautifulSoup4: remove `<script>`, `<style>`, `<nav>`, `<footer>`;
  collect text from `<p>`, `<h1>`–`<h6>`, `<li>`, `<td>` tags; strip excess whitespace
- Page title: from `<title>` tag or first `<h1>`, fallback to hostname
- Upload fetched text content to MinIO as a `.txt` object (required because
  `Document.minio_object_key` is `NOT NULL`). Use `asyncio.to_thread` + existing MinIO
  client pattern from `documents.py`. Object key format: `user_{user_id}/{uuid}.txt`
- Creates `Document` record: `file_type="txt"`, `filename=<page_title>`,
  `source_url=<url>`, `minio_object_key=<object_key>`
  **Required: update `Document` model in `app/db/models.py`** to add:
  `source_url: Mapped[str | None] = mapped_column(Text, nullable=True)`
  AND add migration: `ALTER TABLE documents ADD COLUMN source_url TEXT`
  `file_type` stays `"txt"` — already in the `CheckConstraint`, no constraint change needed.
- Pipes through existing `index_document()` RAG pipeline
- Returns a `DocumentOut` Pydantic schema (must be created — no `DocumentOut` class
  exists in `documents.py` today; the upload endpoint returns a raw `dict`):
  `{ id, filename, file_type, source_url, created_at, workspace_id }`
  Also update the existing upload endpoint to use `DocumentOut` for consistency.

**New dependencies** (must add to `backend/pyproject.toml` via `uv add`):
- `beautifulsoup4>=4.12`
- `lxml>=5.0` (faster BS4 parser)

**Frontend — Documents page**
- Add "Add from URL" button next to "Upload" button
- Modal: URL text input + optional "Add to workspace" selector
- Same success/error handling as file upload

---

## Feature 5: Prompt Template Library

### Problem
Users start every conversation with a blank system — no built-in templates for common
use cases (coding assistant, translator, summarizer, etc.).

### Design

**Frontend only** — no backend needed.

**Data: `src/data/prompt-templates.ts`**
- Typed array of `PromptTemplate` objects:
  `{ id, category, name, description, system_prompt, tags }`
- ~20 built-in templates across 5 categories:
  `productivity | coding | writing | language | analysis`

**UI — two entry points:**

1. **New conversation**: "Browse Templates" button on empty chat state
2. **Chat settings panel**: template picker icon in conversation header

**Template picker modal:**
- Category tabs filter list
- Search/filter input
- Card grid: name + description + tags
- On select: fills system prompt in `ChatInput` (new prop) and opens new conversation
  — OR — applies to current conversation via new `PATCH /api/conversations/{id}` endpoint
  that accepts `{ persona_override: str | null }`. This endpoint must be created (the
  model field exists but no PATCH endpoint currently exists for it).
  Note: `persona_override` exists on BOTH `UserSettings` (line 120) and `Conversation`
  (line ~161) in `models.py`. The correct target is `Conversation.persona_override` —
  this field overrides the default persona for a specific conversation.

---

## Non-Goals (Explicitly Deferred)

- OAuth/SSO — requires auth flow redesign
- Ollama model management UI — needs Ollama daemon running to test
- Hybrid RAG search + re-ranking — requires new ML dependencies
- Semantic memory (Mem0) — new infra dependency
- OpenAI-compatible API endpoint — separate roadmap item
- Mobile responsive layout — CSS-only, but sprawling scope

---

## Architecture Summary

| Feature | Backend | Frontend | DB Migration | New Deps |
|---------|---------|----------|--------------|----------|
| Conv Search | New endpoint | Sidebar search bar | GIN trigram index on messages.content + conversations.title | None |
| Conv Export | New endpoint | Export menu | None | None |
| Image Input | Add backend validation | Upload UI | None | None |
| RAG Citations | Expose tool_calls on ai messages | Citation panel | None | None |
| URL Ingestion | New endpoint | URL input modal | `source_url` column on documents | beautifulsoup4 + lxml |
| Prompt Templates | New PATCH /conversations/{id} | Template library | None | None |

---

## Testing Strategy

- Unit tests for search endpoint (empty query, special chars, no results)
- Unit tests for export endpoint (all three formats, auth check)
- Unit tests for URL ingestion (SSRF block, oversized, successful parse)
- Frontend: existing test patterns (manual verification for UI components)
- All existing tests must continue to pass
