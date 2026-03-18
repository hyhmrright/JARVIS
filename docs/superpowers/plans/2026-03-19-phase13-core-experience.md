# Phase 13: Core Experience Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add conversation search/export, image paste, RAG citations, URL knowledge base ingestion, and prompt templates to close the biggest UX gaps vs Open WebUI / Dify.

**Architecture:** Six self-contained features share one Alembic migration (trigram indexes + source_url column), with backend endpoints added to existing routers and frontend components integrated into existing pages. No new infrastructure required beyond two Python packages (beautifulsoup4, lxml).

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy async / PostgreSQL pg_trgm / httpx / BeautifulSoup4 / Vue 3 / TypeScript / Pinia

**Spec:** `docs/superpowers/specs/2026-03-19-phase13-core-experience-design.md`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `backend/alembic/versions/e5f6a7b8c9d0_phase13_indexes.py` | Create | pg_trgm GIN index + source_url column |
| `backend/app/db/models.py` | Modify | Add `source_url` to `Document` model |
| `backend/app/api/conversations.py` | Modify | Add search, export, PATCH persona_override endpoints |
| `backend/app/api/deps.py` | Modify | Add `get_current_user_optional` helper |
| `backend/app/api/documents.py` | Modify | Add `DocumentOut` schema + `ingest-url` endpoint |
| `backend/app/api/chat.py` | Modify | Add Pydantic validator for image_urls |
| `backend/pyproject.toml` | Modify | Add beautifulsoup4 + lxml |
| `backend/tests/api/test_conversations.py` | Modify/Create | Tests for search + export + PATCH |
| `backend/tests/api/test_documents.py` | Modify/Create | Tests for ingest-url |
| `frontend/src/pages/ChatPage.vue` | Modify | Image paste + size limits + RAG citation panel + search UI |
| `frontend/src/pages/DocumentsPage.vue` | Modify | Add URL ingestion UI |
| `frontend/src/components/PromptTemplateModal.vue` | Create | Template picker modal |
| `frontend/src/data/prompt-templates.ts` | Create | 20 built-in templates |
| `frontend/src/api/index.ts` | Modify | Add search/export/ingest-url/PATCH API calls |


---

## Task 1: DB Migration — trigram indexes + source_url

**Files:**
- Create: `backend/alembic/versions/e5f6a7b8c9d0_phase13_indexes.py`
- Modify: `backend/app/db/models.py` (Document model)

**Context:** The `Document` model is in `app/db/models.py` around line 274. The latest migration is `d4e5f6a7b8c9`. All migrations go in `backend/alembic/versions/`.

- [ ] **Step 1: Add `source_url` to Document model**

In `backend/app/db/models.py`, inside the `Document` class after the `minio_object_key` line (around line 299), add:

```python
source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
```

The import `from sqlalchemy import Text` is likely already present. If not, add it to the existing sqlalchemy imports.

- [ ] **Step 2: Create the Alembic migration**

Create file `backend/alembic/versions/e5f6a7b8c9d0_phase13_indexes.py`:

```python
"""phase13_indexes

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-19 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_messages_content_trgm "
        "ON messages USING GIN (content gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversations_title_trgm "
        "ON conversations USING GIN (title gin_trgm_ops)"
    )
    op.add_column("documents", sa.Column("source_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "source_url")
    op.execute("DROP INDEX IF EXISTS ix_conversations_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_messages_content_trgm")
```

- [ ] **Step 3: Run migration**

```bash
cd backend && uv run alembic upgrade head
```

Expected: `Running upgrade d4e5f6a7b8c9 -> e5f6a7b8c9d0, phase13_indexes`

- [ ] **Step 4: Verify**

```bash
cd backend && uv run ruff check --fix app/db/models.py && uv run mypy app/db/models.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/e5f6a7b8c9d0_phase13_indexes.py backend/app/db/models.py
git commit -m "feat(db): add trigram indexes for search and source_url column for URL ingestion"
```

---

## Task 2: Conversation Search — Backend + Tests

**Files:**
- Modify: `backend/app/api/conversations.py`
- Create/Modify: `backend/tests/api/test_conversations.py`

**Context:** `conversations.py` has imports from `fastapi`, `sqlalchemy`, `pydantic`. The existing endpoints follow the pattern: auth via `Depends(get_current_user)`, DB via `Depends(get_db)`. Look at `list_conversations` as a reference. The `Message` model is imported from `app.db.models`. Add new imports only if they aren't already present.

- [ ] **Step 1: Write failing tests**

If `backend/tests/api/test_conversations.py` doesn't exist, create it. If it exists, append these tests:

```python
import pytest

from app.db.models import Conversation, Message


@pytest.mark.anyio
async def test_search_rejects_single_char(auth_client):
    resp = await auth_client.get("/api/conversations/search?q=a")
    assert resp.status_code == 422  # Pydantic min_length=2 returns 422


@pytest.mark.anyio
async def test_search_returns_empty_list_for_no_match(auth_client):
    resp = await auth_client.get("/api/conversations/search?q=zzznomatch")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_search_finds_conversation_by_title(auth_client, db_session):
    from app.core.security import decode_access_token
    token = auth_client.headers["Authorization"].split(" ")[1]
    user_id = decode_access_token(token)
    conv = Conversation(user_id=user_id, title="Python tutorials for beginners")
    db_session.add(conv)
    await db_session.commit()
    resp = await auth_client.get("/api/conversations/search?q=Python")
    assert resp.status_code == 200
    results = resp.json()
    assert any(r["conv_id"] == str(conv.id) for r in results)
    result = next(r for r in results if r["conv_id"] == str(conv.id))
    assert "title" in result
    assert "snippet" in result
    assert "updated_at" in result


@pytest.mark.anyio
async def test_search_finds_by_message_content(auth_client, db_session):
    from app.core.security import decode_access_token
    token = auth_client.headers["Authorization"].split(" ")[1]
    user_id = decode_access_token(token)
    conv = Conversation(user_id=user_id, title="Generic conversation")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(
        conversation_id=conv.id,
        role="human",
        content="Explain quantum entanglement in simple terms",
    )
    db_session.add(msg)
    await db_session.commit()
    resp = await auth_client.get("/api/conversations/search?q=quantum")
    assert resp.status_code == 200
    assert any(r["conv_id"] == str(conv.id) for r in resp.json())
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && uv run pytest tests/api/test_conversations.py::test_search_rejects_single_char -v
```

Expected: FAIL with 404 (endpoint not found)

- [ ] **Step 3: Implement search endpoint in conversations.py**

Add to existing imports in `backend/app/api/conversations.py`:

```python
from fastapi import Query
from sqlalchemy import or_
```

Add `SearchResult` schema and the endpoint. Insert BEFORE the `/{conv_id}/messages` route so FastAPI matches `/search` before `/{conv_id}`:

```python
class SearchResult(BaseModel):
    conv_id: uuid.UUID
    title: str
    snippet: str
    updated_at: datetime


@router.get("/search", response_model=list[SearchResult])
async def search_conversations(
    q: str = Query(..., min_length=2, description="Search query, min 2 chars"),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SearchResult]:
    """Full-text search across conversation titles and message content."""
    pattern = f"%{q}%"

    title_rows = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id == user.id,
            Conversation.title.ilike(pattern),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    title_convs = list(title_rows.scalars().all())
    title_ids = {c.id for c in title_convs}

    msg_rows = await db.execute(
        select(Message.conversation_id, Message.content)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.user_id == user.id,
            Message.role.in_(["human", "ai"]),
            Message.content.ilike(pattern),
        )
        .order_by(Message.conversation_id, Message.created_at)
        .distinct(Message.conversation_id)
        .limit(limit)
    )
    msg_matches: dict[uuid.UUID, str] = {
        row.conversation_id: row.content for row in msg_rows.all()
    }

    extra_ids = [cid for cid in msg_matches if cid not in title_ids]
    extra_convs: list[Conversation] = []
    if extra_ids:
        extra_rows = await db.execute(
            select(Conversation)
            .where(Conversation.id.in_(extra_ids))
            .order_by(Conversation.updated_at.desc())
        )
        extra_convs = list(extra_rows.scalars().all())

    def _snippet(text: str) -> str:
        idx = text.lower().find(q.lower())
        start = max(0, idx - 50) if idx >= 0 else 0
        return ("..." if start > 0 else "") + text[start : start + 200]

    results: list[SearchResult] = []
    for conv in title_convs + extra_convs:
        snippet_src = msg_matches.get(conv.id, conv.title)
        results.append(
            SearchResult(
                conv_id=conv.id,
                title=conv.title,
                snippet=_snippet(snippet_src),
                updated_at=conv.updated_at,
            )
        )
    return results[:limit]
```

- [ ] **Step 4: Run search tests**

```bash
cd backend && uv run pytest tests/api/test_conversations.py -k "search" -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/conversations.py backend/tests/api/test_conversations.py
git commit -m "feat(api): add conversation search endpoint"
```

---

## Task 3: Conversation Export — Backend + Tests

**Files:**
- Modify: `backend/app/api/conversations.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/tests/api/test_conversations.py`

**Context:** The export endpoint needs to support both authenticated users (via JWT) and anonymous users (via share token). The `SharedConversation` model is already imported in `conversations.py`. Look at `app/api/public.py` for how it looks up shared conversations. The existing `get_current_user` in `deps.py` raises HTTP 401 on invalid/missing token.

- [ ] **Step 1: Add `get_current_user_optional` to deps.py**

Open `backend/app/api/deps.py`. Find the `get_current_user` function. Add this after it:

```python
_security_optional = HTTPBearer(auto_error=False)

async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security_optional),
    db: AsyncSession = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
) -> "User | None":
    """Like get_current_user but returns None instead of raising 401."""
    if not credentials:
        return None
    try:
        return await _resolve_user(credentials.credentials, db, request)
    except HTTPException:
        return None
```

Note: `_resolve_user` is the private helper already used by `get_current_user` in deps.py.
Import `HTTPBearer`, `HTTPAuthorizationCredentials`, and `Request` are already imported there.
Also import `_resolve_user` if it's not already accessible (it's a module-level function in deps.py).

Note: check the actual signature of `get_current_user` in deps.py — copy its parameter names exactly.

- [ ] **Step 2: Write failing export tests**

Append to `backend/tests/api/test_conversations.py`:

```python
import json as _json


@pytest.mark.anyio
async def test_export_markdown_format(auth_client, db_session):
    from app.core.security import decode_access_token
    token = auth_client.headers["Authorization"].split(" ")[1]
    user_id = decode_access_token(token)
    conv = Conversation(user_id=user_id, title="My Export Test")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(Message(conversation_id=conv.id, role="human", content="Hello AI"))
    db_session.add(Message(conversation_id=conv.id, role="ai", content="Hello human"))
    await db_session.commit()
    resp = await auth_client.get(f"/api/conversations/{conv.id}/export?format=md")
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    assert "My Export Test" in resp.text
    assert "**Human:**" in resp.text
    assert "**Assistant:**" in resp.text
    assert "Hello AI" in resp.text


@pytest.mark.anyio
async def test_export_json_format(auth_client, db_session):
    from app.core.security import decode_access_token
    token = auth_client.headers["Authorization"].split(" ")[1]
    user_id = decode_access_token(token)
    conv = Conversation(user_id=user_id, title="JSON Export")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(Message(conversation_id=conv.id, role="human", content="Question"))
    await db_session.commit()
    resp = await auth_client.get(f"/api/conversations/{conv.id}/export?format=json")
    assert resp.status_code == 200
    data = _json.loads(resp.content)
    assert data["title"] == "JSON Export"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == "human"


@pytest.mark.anyio
async def test_export_txt_format(auth_client, db_session):
    from app.core.security import decode_access_token
    token = auth_client.headers["Authorization"].split(" ")[1]
    user_id = decode_access_token(token)
    conv = Conversation(user_id=user_id, title="TXT Export")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(Message(conversation_id=conv.id, role="human", content="Test msg"))
    await db_session.commit()
    resp = await auth_client.get(f"/api/conversations/{conv.id}/export?format=txt")
    assert resp.status_code == 200
    assert "Human: Test msg" in resp.text


@pytest.mark.anyio
async def test_export_returns_404_for_wrong_user(auth_client, second_user_auth_headers, db_session):
    from app.core.security import decode_access_token
    # Create a conversation owned by second user
    token2 = second_user_auth_headers["Authorization"].split(" ")[1]
    user2_id = decode_access_token(token2)
    conv = Conversation(user_id=user2_id, title="Private")
    db_session.add(conv)
    await db_session.commit()
    # Try to export as first user (auth_client)
    resp = await auth_client.get(f"/api/conversations/{conv.id}/export")
    assert resp.status_code == 404
```

- [ ] **Step 3: Run to verify they fail**

```bash
cd backend && uv run pytest tests/api/test_conversations.py -k "export" -v
```

Expected: FAIL (endpoint not found)

- [ ] **Step 4: Implement export endpoint in conversations.py**

Add new imports at top of `conversations.py` (only if not already present):

```python
import json as _json
from fastapi.responses import Response
from app.api.deps import get_current_user_optional
```

Add the endpoint AFTER the `search_conversations` endpoint:

```python
@router.get("/{conv_id}/export")
async def export_conversation(
    conv_id: uuid.UUID,
    format: str = Query("md", pattern="^(md|json|txt)$"),
    token: str | None = Query(None, description="Share token for public access"),
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export conversation as Markdown, JSON, or plain text."""
    conv: Conversation | None = None

    if user:
        conv = await db.scalar(
            select(Conversation).where(
                Conversation.id == conv_id, Conversation.user_id == user.id
            )
        )
    if not conv and token:
        shared = await db.scalar(
            select(SharedConversation).where(SharedConversation.share_token == token)
        )
        if shared:
            conv = await db.get(Conversation, shared.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    rows = await db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conv_id,
            Message.role.in_(["human", "ai"]),
        )
        .order_by(Message.created_at)
    )
    messages = list(rows.all())
    safe_title = conv.title.replace("/", "_").replace("\\", "_")

    if format == "md":
        lines = [f"# {conv.title}", ""]
        for msg in messages:
            prefix = "**Human:**" if msg.role == "human" else "**Assistant:**"
            lines.append(f"{prefix}\n{msg.content}")
            lines.append("")
        return Response(
            content="\n".join(lines),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
        )
    elif format == "json":
        data = {
            "id": str(conv.id),
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                }
                for msg in messages
            ],
        }
        return Response(
            content=_json.dumps(data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.json"'},
        )
    else:  # txt
        lines = []
        for msg in messages:
            prefix = "Human" if msg.role == "human" else "Assistant"
            lines.append(f"{prefix}: {msg.content}")
            lines.append("")
        return Response(
            content="\n".join(lines),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.txt"'},
        )
```

- [ ] **Step 5: Run export tests**

```bash
cd backend && uv run pytest tests/api/test_conversations.py -k "export" -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/conversations.py backend/app/api/deps.py backend/tests/api/test_conversations.py
git commit -m "feat(api): add conversation export endpoint (md/json/txt) with optional share token"
```

---

## Task 4: PATCH Conversation Endpoint

**Files:**
- Modify: `backend/app/api/conversations.py`
- Modify: `backend/tests/api/test_conversations.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/api/test_conversations.py`:

```python
@pytest.mark.anyio
async def test_patch_conversation_sets_persona(auth_client, db_session):
    from app.core.security import decode_access_token
    import sqlalchemy as sa
    from app.db.models import Conversation as Conv
    token = auth_client.headers["Authorization"].split(" ")[1]
    user_id = decode_access_token(token)
    conv = Conversation(user_id=user_id, title="Patch test")
    db_session.add(conv)
    await db_session.commit()
    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}",
        json={"persona_override": "You are a Socratic tutor."},
    )
    assert resp.status_code == 204
    await db_session.refresh(conv)
    assert conv.persona_override == "You are a Socratic tutor."


@pytest.mark.anyio
async def test_patch_conversation_clears_persona(auth_client, db_session):
    from app.core.security import decode_access_token
    token = auth_client.headers["Authorization"].split(" ")[1]
    user_id = decode_access_token(token)
    conv = Conversation(user_id=user_id, title="Clear test", persona_override="Old value")
    db_session.add(conv)
    await db_session.commit()
    resp = await auth_client.patch(
        f"/api/conversations/{conv.id}",
        json={"persona_override": None},
    )
    assert resp.status_code == 204
    await db_session.refresh(conv)
    assert conv.persona_override is None
```

- [ ] **Step 2: Verify tests fail**

```bash
cd backend && uv run pytest tests/api/test_conversations.py -k "patch_conversation" -v
```

- [ ] **Step 3: Implement endpoint**

In `backend/app/api/conversations.py`, add after `ConversationOut`:

```python
class ConversationUpdate(BaseModel):
    persona_override: str | None = None
```

Add endpoint after `set_active_leaf`:

```python
@router.patch("/{conv_id}", status_code=204)
async def update_conversation(
    conv_id: uuid.UUID,
    body: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Update mutable conversation fields (currently: persona_override)."""
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user.id
        )
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.persona_override = body.persona_override
    await db.commit()
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/api/test_conversations.py -k "patch_conversation" -v
```

- [ ] **Step 5: Run ALL conversation tests**

```bash
cd backend && uv run pytest tests/api/test_conversations.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/conversations.py backend/tests/api/test_conversations.py
git commit -m "feat(api): add PATCH /conversations/{id} for persona_override"
```

---

## Task 5: Image Validation + Paste — Backend + Frontend

**Part A — Backend validator**

**Files:**
- Modify: `backend/app/api/chat.py`

**Context:** `ChatRequest` class is around line 285 in `chat.py`. It already has `image_urls: list[str] | None = None`. Add a Pydantic field_validator. The file imports from pydantic — add `field_validator` to that import.

- [ ] **Step 1: Add validator to ChatRequest**

In `backend/app/api/chat.py`:

1. Update the pydantic import: change `from pydantic import BaseModel` to `from pydantic import BaseModel, field_validator`

2. Inside the `ChatRequest` class, after `image_urls: list[str] | None = None`, add:

```python
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
```

- [ ] **Step 2: Verify ruff + mypy**

```bash
cd backend && uv run ruff check --fix app/api/chat.py && uv run mypy app/api/chat.py
```

- [ ] **Step 3: Commit backend change**

```bash
git add backend/app/api/chat.py
git commit -m "feat(chat): add backend validation for image count and size limits"
```

**Part B — Frontend paste handler**

**Files:**
- Modify: `frontend/src/pages/ChatPage.vue`

**Context:** ChatPage.vue already has: file input (`fileInput` ref), `handleImageSelect` function, `selectedImages` ref (string array of base64 data URLs), image preview strip. It does NOT have: paste-from-clipboard, size/count limit enforcement.

- [ ] **Step 4: Add `addImages` helper and `handlePaste`**

In the `<script setup>` section of `ChatPage.vue`, find the `handleImageSelect` function (around line 454) and replace the entire function plus add new functions:

```typescript
const MAX_IMAGES = 4;
const MAX_IMAGE_BYTES = 4 * 1024 * 1024;

const addImages = (files: File[]) => {
  for (const file of files) {
    if (selectedImages.value.length >= MAX_IMAGES) {
      alert(`Maximum ${MAX_IMAGES} images per message`);
      break;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      alert(`"${file.name}" exceeds 4 MB`);
      continue;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      if (ev.target?.result) {
        selectedImages.value.push(ev.target.result as string);
      }
    };
    reader.readAsDataURL(file);
  }
};

const handleImageSelect = (e: Event) => {
  const files = (e.target as HTMLInputElement).files;
  if (!files) return;
  addImages(Array.from(files));
  if (fileInput.value) fileInput.value.value = '';
};

const removeImage = (idx: number) => {
  selectedImages.value.splice(idx, 1);
};

const handlePaste = (e: ClipboardEvent) => {
  const items = e.clipboardData?.items;
  if (!items) return;
  const imageFiles: File[] = [];
  for (const item of Array.from(items)) {
    if (item.type.startsWith("image/")) {
      const file = item.getAsFile();
      if (file) imageFiles.push(file);
    }
  }
  if (imageFiles.length > 0) {
    e.preventDefault();
    addImages(imageFiles);
  }
};
```

- [ ] **Step 5: Add `@paste` to the textarea**

Find the textarea element in the template. It has `@keydown.enter="handleEnter"`. Add `@paste="handlePaste"` to it.

- [ ] **Step 6: Type-check**

```bash
cd frontend && bun run type-check
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ChatPage.vue
git commit -m "feat(frontend): add image paste from clipboard with 4MB/4-image limit"
```

---

## Task 6: RAG Source Citations — Backend + Frontend

**Files:**
- Modify: `backend/app/api/conversations.py` (MessageOut schema)
- Modify: `backend/tests/api/test_conversations.py`
- Modify: `frontend/src/pages/ChatPage.vue`

**Context:** `MessageOut` currently exposes: id, role, content, parent_id, image_urls, created_at. The `Message` DB model has `tool_calls: Mapped[dict[str, Any] | None]` which is already stored but not returned in the API. LangChain serializes AI message tool calls as: `[{"name": "rag_search", "id": "call_xyz", "args": {...}}]`. The rag_search tool returns formatted text like: `[1] Document: "filename.pdf" (relevance: 0.87)\nchunk content here`.

- [ ] **Step 1: Write test for tool_calls exposure**

Append to `backend/tests/api/test_conversations.py`:

```python
@pytest.mark.anyio
async def test_messages_include_tool_calls_field(auth_client, db_session):
    from app.core.security import decode_access_token
    from typing import Any
    token = auth_client.headers["Authorization"].split(" ")[1]
    user_id = decode_access_token(token)
    conv = Conversation(user_id=user_id, title="Tool calls test")
    db_session.add(conv)
    await db_session.flush()
    tool_calls_data: list[dict[str, Any]] = [
        {"name": "rag_search", "id": "call_abc123", "args": {"query": "test"}}
    ]
    ai_msg = Message(
        conversation_id=conv.id,
        role="ai",
        content="Here are the results.",
        tool_calls=tool_calls_data,
    )
    db_session.add(ai_msg)
    await db_session.commit()
    resp = await auth_client.get(f"/api/conversations/{conv.id}/messages")
    assert resp.status_code == 200
    msgs = resp.json()
    ai = next(m for m in msgs if m["role"] == "ai")
    assert "tool_calls" in ai
    assert ai["tool_calls"][0]["name"] == "rag_search"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && uv run pytest tests/api/test_conversations.py::test_messages_include_tool_calls_field -v
```

Expected: FAIL (tool_calls not in response)

- [ ] **Step 3: Add tool_calls to MessageOut**

In `backend/app/api/conversations.py`, find `class MessageOut` and update it:

```python
from typing import Any

class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    parent_id: uuid.UUID | None = None
    image_urls: list[str] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    created_at: datetime
    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Run the test**

```bash
cd backend && uv run pytest tests/api/test_conversations.py::test_messages_include_tool_calls_field -v
```

Expected: PASS

- [ ] **Step 5: Add Sources panel to ChatPage.vue**

In `ChatPage.vue` `<script setup>`, add:

```typescript
import { ChevronDown } from 'lucide-vue-next';

const openSources = ref(new Set<string>());
const toggleSources = (msgId: string) => {
  const s = new Set(openSources.value);
  if (s.has(msgId)) s.delete(msgId);
  else s.add(msgId);
  openSources.value = s;
};

interface RagSource { name: string; score: number; snippet: string }

const getRagSources = (msg: { id: string; role: string; tool_calls?: Array<{name: string; id?: string}> | null }): RagSource[] => {
  if (msg.role !== 'ai' || !msg.tool_calls) return [];
  const ragCall = msg.tool_calls.find((tc) => tc.name === 'rag_search');
  if (!ragCall) return [];

  const msgIdx = chat.messages.findIndex((m) => m.id === msg.id);
  if (msgIdx === -1) return [];

  const sources: RagSource[] = [];
  for (let i = msgIdx + 1; i < chat.messages.length; i++) {
    const m = chat.messages[i];
    if (m.role !== 'tool') break;
    const re = /\[(\d+)\] Document: "([^"]+)" \(relevance: ([\d.]+)\)\n([\s\S]*?)(?=\[\d+\] Document:|$)/g;
    let match;
    while ((match = re.exec(m.content)) !== null) {
      sources.push({ name: match[2], score: parseFloat(match[3]), snippet: match[4].trim().slice(0, 150) });
    }
    break;
  }
  return sources;
};
```

In the template, find where AI message content is rendered and add AFTER the message content:

```html
<!-- RAG Sources -->
<template v-if="msg.role === 'ai' && getRagSources(msg).length > 0">
  <div class="mt-2 border-t border-zinc-800 pt-2">
    <button
      class="flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-300 transition-colors"
      @click="toggleSources(msg.id)"
    >
      <ChevronDown
        class="w-3 h-3 transition-transform duration-200"
        :class="openSources.has(msg.id) ? 'rotate-180' : ''"
      />
      {{ getRagSources(msg).length }} source{{ getRagSources(msg).length > 1 ? 's' : '' }}
    </button>
    <div v-if="openSources.has(msg.id)" class="mt-2 space-y-2">
      <div
        v-for="(src, si) in getRagSources(msg)"
        :key="si"
        class="rounded-md bg-zinc-800/50 border border-zinc-700/40 p-2.5 text-xs"
      >
        <div class="text-zinc-200 font-medium mb-0.5">{{ src.name }}</div>
        <div class="text-zinc-500 text-[11px] mb-1">{{ Math.round(src.score * 100) }}% relevance</div>
        <div class="text-zinc-400 line-clamp-3">{{ src.snippet }}</div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 6: Type-check + run all backend conversation tests**

```bash
cd frontend && bun run type-check
cd backend && uv run pytest tests/api/test_conversations.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/conversations.py backend/tests/api/test_conversations.py frontend/src/pages/ChatPage.vue
git commit -m "feat: expose tool_calls in MessageOut and add RAG source citations panel"
```

---

## Task 7: URL Knowledge Base Ingestion — Backend

**Files:**
- Modify: `backend/pyproject.toml` + `backend/uv.lock`
- Modify: `backend/app/api/documents.py`
- Create/Modify: `backend/tests/api/test_documents.py`

**Context:** `documents.py` already uses `httpx` (check — it might not be directly imported; it uses `asyncio`, `io`, `uuid`, MinIO, Qdrant, and `index_document`). The `is_safe_url` function is in `app.tools.web_fetch_tool`. The MinIO upload pattern is: `await asyncio.to_thread(minio_client.put_object, settings.minio_bucket, object_key, io.BytesIO(content), len(content))`. Object key format used: `f"{user.id}/{uuid.uuid4()}_{safe_name}"`.

- [ ] **Step 1: Add dependencies**

```bash
cd backend && uv add "beautifulsoup4>=4.12" "lxml>=5.0"
```

Expected: packages added to `pyproject.toml` and `uv.lock` updated.

- [ ] **Step 2: Write failing tests**

If `backend/tests/api/test_documents.py` doesn't exist, create it. Add:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.anyio
async def test_ingest_url_blocks_private_ip(auth_client):
    resp = await auth_client.post(
        "/api/documents/ingest-url",
        json={"url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert resp.status_code == 400
    assert "not allowed" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_ingest_url_blocks_localhost(auth_client):
    resp = await auth_client.post(
        "/api/documents/ingest-url",
        json={"url": "http://localhost:8080/secret"},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_ingest_url_rejects_non_http(auth_client):
    resp = await auth_client.post(
        "/api/documents/ingest-url",
        json={"url": "file:///etc/passwd"},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_ingest_url_success(auth_client, db_session):
    html_content = (
        b"<html><head><title>ML Guide</title></head>"
        b"<body><p>Machine learning is fascinating.</p></body></html>"
    )
    mock_resp = MagicMock()
    mock_resp.content = html_content
    mock_resp.raise_for_status = MagicMock()

    with (
        patch("app.api.documents.httpx") as mock_httpx,
        patch("app.api.documents.asyncio.to_thread", side_effect=[("ML Guide", "Machine learning is fascinating."), None]),
        patch("app.api.documents.index_document", new=AsyncMock(return_value=5)),
        patch("app.api.documents.resolve_api_key", return_value="sk-fake"),
    ):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_ctx.get = AsyncMock(return_value=mock_resp)
        mock_httpx.AsyncClient.return_value = mock_ctx

        resp = await auth_client.post(
            "/api/documents/ingest-url",
            json={"url": "https://example.com/ml-guide"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["file_type"] == "txt"
    assert data["source_url"] == "https://example.com/ml-guide"
    assert "filename" in data
```

- [ ] **Step 3: Verify tests fail**

```bash
cd backend && uv run pytest tests/api/test_documents.py -k "ingest_url" -v
```

Expected: FAIL

- [ ] **Step 4: Add DocumentOut schema and ingest-url endpoint to documents.py**

First, update the EXISTING upload endpoint's return statement. Find `return {"id": str(doc.id), "filename": doc.filename, "chunk_count": chunk_count}` at the bottom of `upload_document` and replace with:

```python
return DocumentOut.model_validate(doc)
```

Also add `response_model=DocumentOut` to the `@router.post("/upload", ...)` decorator (replace the existing return type annotation).

Then add these imports at the top of `backend/app/api/documents.py`:

```python
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from pydantic import BaseModel

from app.tools.web_fetch_tool import is_safe_url
```

Add `DocumentOut` schema after the imports, before the router:

```python
class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    source_url: str | None = None
    file_size_bytes: int
    chunk_count: int
    created_at: datetime
    workspace_id: uuid.UUID | None = None
    model_config = {"from_attributes": True}
```

Add the endpoint at the end of `documents.py`:

```python
class IngestUrlRequest(BaseModel):
    url: str
    workspace_id: uuid.UUID | None = None


_MAX_URL_CONTENT_BYTES = 5 * 1024 * 1024  # 5 MB


def _extract_page_text(html_bytes: bytes) -> tuple[str, str]:
    """Return (title, body_text) from HTML. Strips noise, collects content tags."""
    soup = BeautifulSoup(html_bytes, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
    parts = []
    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td"]):
        text = tag.get_text(separator=" ", strip=True)
        if text:
            parts.append(text)
    return title or "Web Page", "\n\n".join(parts)


@router.post("/ingest-url", response_model=DocumentOut, status_code=201)
async def ingest_url(
    body: IngestUrlRequest,
    user: User = Depends(get_current_user),
    llm: ResolvedLLMConfig = Depends(get_llm_config),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    """Fetch a web page and add it to the knowledge base."""
    if not is_safe_url(body.url):
        raise HTTPException(
            status_code=400,
            detail=f"URL not allowed (internal or non-http): {body.url!r}",
        )

    qdrant_collection = user_collection_name(str(user.id))
    workspace_id = body.workspace_id

    if workspace_id is not None:
        ws = await db.get(Workspace, workspace_id)
        if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
            raise HTTPException(status_code=404, detail="Workspace not found")
        membership = await db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user.id,
            )
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Not a workspace member")
        qdrant_collection = f"workspace_{workspace_id}"

    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        try:
            response = await client.get(body.url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}") from e

    if len(response.content) > _MAX_URL_CONTENT_BYTES:
        raise HTTPException(status_code=400, detail="Page too large (max 5 MB)")

    title, text = await asyncio.to_thread(_extract_page_text, response.content)
    if not text.strip():
        raise HTTPException(status_code=400, detail="No readable content found on page")

    text_bytes = text.encode("utf-8")
    object_key = f"{user.id}/{uuid.uuid4()}_webpage.txt"

    minio_client = get_minio_client()
    await asyncio.to_thread(
        minio_client.put_object,
        settings.minio_bucket,
        object_key,
        io.BytesIO(text_bytes),
        len(text_bytes),
    )

    openai_key = resolve_api_key("openai", llm.raw_keys)
    if not openai_key:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key required for document embedding. Configure it in Settings.",
        )

    doc = Document(
        user_id=user.id,
        filename=title[:255],
        file_type="txt",
        file_size_bytes=len(text_bytes),
        qdrant_collection=qdrant_collection,
        minio_object_key=object_key,
        source_url=body.url,
    )
    if workspace_id is not None:
        doc.workspace_id = workspace_id
    db.add(doc)
    await db.flush()

    chunk_count = await index_document(
        str(user.id),
        str(doc.id),
        text,
        openai_key,
        doc_name=title,
        collection_name=qdrant_collection,
    )
    doc.chunk_count = chunk_count
    await db.commit()
    logger.info("document_url_ingested", user_id=str(user.id), doc_id=str(doc.id), url=body.url)
    return DocumentOut.model_validate(doc)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/api/test_documents.py -k "ingest_url" -v
```

Expected: PASS

- [ ] **Step 6: Run ruff + mypy**

```bash
cd backend && uv run ruff check --fix app/api/documents.py && uv run mypy app/api/documents.py
```

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/api/documents.py backend/tests/api/test_documents.py
git commit -m "feat(api): add URL knowledge base ingestion with SSRF protection and BS4 extraction"
```

---

## Task 8: Frontend — Search UI, Export Button, URL Ingestion, API client

**Files:**
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/pages/ChatPage.vue`
- Modify: `frontend/src/pages/DocumentsPage.vue`

**Context:** `src/api/index.ts` exports an Axios instance and typed API functions. The pattern is: `export const fnName = (params) => api.get/post<ResponseType>('/path', ...)`. The `ChatPage.vue` has a sidebar with a `<nav>` element showing `chat.conversations`. The `DocumentsPage.vue` has an upload button.

- [ ] **Step 1: Add API functions to api/index.ts**

```typescript
// Conversation search
export const searchConversations = (q: string, limit = 20) =>
  api.get<Array<{ conv_id: string; title: string; snippet: string; updated_at: string }>>(
    "/conversations/search",
    { params: { q, limit } }
  );

// Conversation export (returns Blob)
export const exportConversation = (convId: string, format: "md" | "json" | "txt") =>
  api.get(`/conversations/${convId}/export`, {
    params: { format },
    responseType: "blob",
  });

// PATCH conversation
export const patchConversation = (convId: string, data: { persona_override?: string | null }) =>
  api.patch(`/conversations/${convId}`, data);

// URL ingestion
export const ingestDocumentUrl = (url: string, workspaceId?: string | null) =>
  api.post("/documents/ingest-url", { url, workspace_id: workspaceId ?? null });
```

- [ ] **Step 2: Add search to ChatPage.vue sidebar**

In `<script setup>`, add imports and state:

```typescript
import { Search, X, Download } from 'lucide-vue-next';
import { searchConversations, exportConversation } from '@/api';
import { nextTick, watch } from 'vue';

const searchMode = ref(false);
const searchQuery = ref('');
const searchResults = ref<Array<{ conv_id: string; title: string; snippet: string }>>([]);
const searchInputEl = ref<HTMLInputElement>();

const clearSearch = () => {
  searchMode.value = false;
  searchQuery.value = '';
  searchResults.value = [];
};

let searchTimer: ReturnType<typeof setTimeout> | undefined;
watch(searchQuery, (q) => {
  if (searchTimer) clearTimeout(searchTimer);
  if (q.length < 2) { searchResults.value = []; return; }
  searchTimer = setTimeout(async () => {
    try {
      const resp = await searchConversations(q);
      searchResults.value = resp.data;
    } catch { /* ignore */ }
  }, 300);
});

watch(searchMode, async (on) => {
  if (on) { await nextTick(); searchInputEl.value?.focus(); }
});

const exportConv = async (convId: string, title: string) => {
  const resp = await exportConversation(convId, 'md');
  const url = URL.createObjectURL(resp.data as Blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${title}.md`;
  a.click();
  URL.revokeObjectURL(url);
};
```

- [ ] **Step 3: Update sidebar template for search**

In the template, find the sidebar header `<div class="h-14 ...">` and replace with:

```html
<div class="h-14 flex items-center px-4 justify-between">
  <template v-if="!searchMode">
    <div class="flex items-center gap-2 font-semibold tracking-tighter">
      <div class="w-5 h-5 bg-white text-black rounded-sm flex items-center justify-center text-[10px] font-bold">J</div>
      <span class="text-sm text-zinc-100">JARVIS</span>
    </div>
    <div class="flex items-center gap-1">
      <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors" title="Search" @click="searchMode = true">
        <Search class="w-4 h-4 text-zinc-400" />
      </button>
      <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors" title="New Chat" @click="chat.newConversation">
        <SquarePen class="w-4 h-4 text-zinc-400" />
      </button>
    </div>
  </template>
  <template v-else>
    <input
      ref="searchInputEl"
      v-model="searchQuery"
      type="text"
      placeholder="Search conversations..."
      class="flex-1 bg-zinc-800 rounded-md px-3 py-1.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none"
      @keydown.escape="clearSearch"
    />
    <button class="ml-2 p-1.5 hover:bg-zinc-800 rounded transition-colors" @click="clearSearch">
      <X class="w-4 h-4 text-zinc-400" />
    </button>
  </template>
</div>
```

- [ ] **Step 4: Update sidebar nav to show search results vs conversation list**

Find the `<nav>` element and wrap the existing conversation list:

```html
<nav class="flex-1 overflow-y-auto px-2 py-4 space-y-0.5 custom-scrollbar">
  <!-- Search results mode -->
  <template v-if="searchMode && searchQuery.length >= 2">
    <div v-if="searchResults.length === 0" class="text-center py-8 text-xs text-zinc-500">
      No results found
    </div>
    <div
      v-for="r in searchResults"
      :key="r.conv_id"
      class="flex flex-col gap-0.5 px-3 py-2 rounded-md cursor-pointer transition-colors text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
      @click="chat.selectConversation(r.conv_id); clearSearch()"
    >
      <span class="text-xs font-medium text-zinc-200 truncate">{{ r.title }}</span>
      <span class="text-[11px] text-zinc-500 truncate">{{ r.snippet }}</span>
    </div>
  </template>
  <!-- Normal conversation list -->
  <template v-else>
    <div
      v-for="c in chat.conversations"
      :key="c.id"
      :class="[...]"
      @click="chat.selectConversation(c.id)"
    >
      <MessageSquare class="w-3.5 h-3.5 flex-shrink-0" />
      <span class="text-xs truncate flex-1">{{ c.title }}</span>
      <button
        class="opacity-0 group-hover:opacity-100 p-1 hover:text-zinc-200"
        title="Export"
        @click.stop="exportConv(c.id, c.title)"
      >
        <Download class="w-3 h-3" />
      </button>
      <button
        class="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400"
        @click.stop="chat.deleteConversation(c.id)"
      >
        <Trash2 class="w-3 h-3" />
      </button>
    </div>
  </template>
</nav>
```

Note: preserve the exact classes from the CURRENT conversation item (copy `class` from existing `v-for` loop).

- [ ] **Step 5: Add URL ingestion to DocumentsPage.vue**

Read the current DocumentsPage.vue first to understand the button/layout structure:

```bash
grep -n "upload\|button\|modal\|ref\|import\|<div" frontend/src/pages/DocumentsPage.vue | head -40
```

Then add a "From URL" button near the upload button with this pattern:

In `<script setup>`:

```typescript
import { Link } from 'lucide-vue-next';
import { ingestDocumentUrl } from '@/api';

const showUrlModal = ref(false);
const urlInput = ref('');
const urlIngesting = ref(false);
const urlError = ref('');

const handleIngestUrl = async () => {
  if (!urlInput.value) return;
  urlIngesting.value = true;
  urlError.value = '';
  try {
    await ingestDocumentUrl(urlInput.value);
    showUrlModal.value = false;
    urlInput.value = '';
    await loadDocuments(); // call existing function to refresh list
  } catch (e: any) {
    urlError.value = e?.response?.data?.detail ?? 'Failed to ingest URL';
  } finally {
    urlIngesting.value = false;
  }
};
```

In template, add button and modal:

```html
<!-- "From URL" button — place next to existing upload button -->
<button
  class="flex items-center gap-2 px-3 py-1.5 text-xs rounded-md bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
  @click="showUrlModal = true"
>
  <Link class="w-3.5 h-3.5" />
  From URL
</button>

<!-- URL Modal -->
<div
  v-if="showUrlModal"
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
  @click.self="showUrlModal = false"
>
  <div class="bg-zinc-900 border border-zinc-700 rounded-xl p-6 w-full max-w-md shadow-xl">
    <h3 class="text-sm font-semibold text-zinc-100 mb-4">Add Web Page to Knowledge Base</h3>
    <input
      v-model="urlInput"
      type="url"
      placeholder="https://example.com/article"
      class="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 mb-4"
      @keydown.enter="handleIngestUrl"
    />
    <p v-if="urlError" class="text-xs text-red-400 mb-3">{{ urlError }}</p>
    <div class="flex justify-end gap-2">
      <button class="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-100" @click="showUrlModal = false">
        Cancel
      </button>
      <button
        :disabled="!urlInput || urlIngesting"
        class="px-4 py-1.5 text-xs bg-white text-black rounded-md disabled:opacity-30 hover:bg-zinc-200"
        @click="handleIngestUrl"
      >
        {{ urlIngesting ? 'Adding...' : 'Add Page' }}
      </button>
    </div>
  </div>
</div>
```

- [ ] **Step 6: Type-check + lint**

```bash
cd frontend && bun run type-check && bun run lint:fix
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/index.ts frontend/src/pages/ChatPage.vue frontend/src/pages/DocumentsPage.vue
git commit -m "feat(frontend): add conversation search/export and URL knowledge base ingestion"
```

---

## Task 9: Prompt Template Library

**Files:**
- Create: `frontend/src/data/prompt-templates.ts`
- Create: `frontend/src/components/PromptTemplateModal.vue`
- Modify: `frontend/src/pages/ChatPage.vue`

- [ ] **Step 1: Create data file**

Create `frontend/src/data/prompt-templates.ts`:

```typescript
export interface PromptTemplate {
  id: string;
  category: "productivity" | "coding" | "writing" | "language" | "analysis";
  name: string;
  description: string;
  system_prompt: string;
  tags: string[];
}

export const PROMPT_TEMPLATES: PromptTemplate[] = [
  {
    id: "coding-assistant",
    category: "coding",
    name: "Coding Assistant",
    description: "Expert programmer for all languages and frameworks",
    system_prompt: "You are an expert software engineer. Provide clear, efficient, well-commented code. Explain your choices, prefer modern best practices, and point out potential issues.",
    tags: ["code", "programming", "debug"],
  },
  {
    id: "code-reviewer",
    category: "coding",
    name: "Code Reviewer",
    description: "Critical code review with security and performance focus",
    system_prompt: "You are a senior code reviewer. Analyze code for bugs, security vulnerabilities, performance issues, and maintainability. Be specific and constructive. Provide concrete improvement examples.",
    tags: ["review", "security", "refactor"],
  },
  {
    id: "sql-expert",
    category: "coding",
    name: "SQL Expert",
    description: "Database query optimization and schema design",
    system_prompt: "You are a database expert specializing in SQL. Help write efficient queries, design schemas, optimize performance, and explain execution plans. Support PostgreSQL, MySQL, and SQLite.",
    tags: ["sql", "database", "query"],
  },
  {
    id: "system-design",
    category: "coding",
    name: "System Design Expert",
    description: "Architecture and system design for scale",
    system_prompt: "You are a distributed systems expert. Help design scalable, reliable systems. Discuss CAP theorem tradeoffs, databases, caching, queuing, and API design. Use ASCII diagrams when helpful.",
    tags: ["architecture", "design", "scalability"],
  },
  {
    id: "linux-devops",
    category: "coding",
    name: "Linux & DevOps Expert",
    description: "Linux, shell scripting, and DevOps workflows",
    system_prompt: "You are a Linux and DevOps expert. Help with shell scripting, system administration, Docker, Kubernetes, CI/CD pipelines, and infrastructure as code. Provide working commands with clear explanations. Warn when commands could be destructive.",
    tags: ["linux", "devops", "shell", "docker"],
  },
  {
    id: "translator",
    category: "language",
    name: "Precise Translator",
    description: "Accurate translation preserving tone and nuance",
    system_prompt: "You are a professional translator. Translate text accurately while preserving tone, style, and nuance. Note any cultural differences or non-trivial translation choices you make.",
    tags: ["translate", "language", "multilingual"],
  },
  {
    id: "english-tutor",
    category: "language",
    name: "English Writing Coach",
    description: "Improve English writing with detailed feedback",
    system_prompt: "You are an English writing coach. Help improve clarity, grammar, vocabulary, and style. Provide specific feedback and rewritten examples. Explain the reasoning behind each suggestion.",
    tags: ["english", "grammar", "writing"],
  },
  {
    id: "summarizer",
    category: "productivity",
    name: "Smart Summarizer",
    description: "Concise summaries with key points highlighted",
    system_prompt: "You are an expert at distilling information. Create concise, structured summaries that capture key points, main arguments, and important details. Use bullet points for clarity.",
    tags: ["summary", "tldr", "notes"],
  },
  {
    id: "meeting-notes",
    category: "productivity",
    name: "Meeting Notes Organizer",
    description: "Structure raw notes into decisions and action items",
    system_prompt: "You organize meeting notes into clear structured summaries. Extract: 1) Key decisions made, 2) Action items with owners and deadlines, 3) Discussion points, 4) Next steps. Format as clean markdown.",
    tags: ["meetings", "notes", "productivity"],
  },
  {
    id: "product-manager",
    category: "productivity",
    name: "Product Manager",
    description: "Product strategy, user stories, and roadmaps",
    system_prompt: "You think like an experienced product manager. Help define user stories, prioritize features, identify user needs, and structure product roadmaps. Apply RICE scoring, Jobs-to-be-Done, and user journey mapping.",
    tags: ["product", "strategy", "roadmap"],
  },
  {
    id: "startup-advisor",
    category: "productivity",
    name: "Startup Advisor",
    description: "Direct advice on building and scaling startups",
    system_prompt: "You are a seasoned startup advisor. Give direct, actionable advice on product-market fit, growth, fundraising, team building, and avoiding common pitfalls. Be honest about hard truths.",
    tags: ["startup", "business", "growth"],
  },
  {
    id: "email-writer",
    category: "writing",
    name: "Professional Email Writer",
    description: "Clear, professional emails for any situation",
    system_prompt: "You write professional emails that are clear, concise, and appropriately toned. Match formality to context. Ensure every email has a clear purpose, relevant details, and a specific call-to-action.",
    tags: ["email", "business", "communication"],
  },
  {
    id: "copywriter",
    category: "writing",
    name: "Marketing Copywriter",
    description: "Persuasive copy for products and campaigns",
    system_prompt: "You are a skilled marketing copywriter. Write compelling, conversion-focused copy. Focus on benefits over features, use active voice, and tailor language to the target audience.",
    tags: ["marketing", "copywriting", "ads"],
  },
  {
    id: "technical-writer",
    category: "writing",
    name: "Technical Documentation Writer",
    description: "Clear READMEs, API docs, and technical guides",
    system_prompt: "You write clear, comprehensive technical documentation. Structure content logically with headings, code examples, and step-by-step instructions. Follow docs-as-code best practices.",
    tags: ["docs", "readme", "technical"],
  },
  {
    id: "creative-writer",
    category: "writing",
    name: "Creative Writer",
    description: "Stories, fiction, and creative content",
    system_prompt: "You are a versatile creative writer. Help craft compelling narratives, develop characters, build worlds, and write in various genres and tones. Offer creative suggestions to overcome writer's block.",
    tags: ["creative", "fiction", "storytelling"],
  },
  {
    id: "data-analyst",
    category: "analysis",
    name: "Data Analyst",
    description: "Analyze data patterns and provide actionable insights",
    system_prompt: "You are a data analyst. Interpret data, identify patterns and trends, suggest appropriate visualizations, and provide actionable insights. Explain statistical concepts clearly and always note data limitations.",
    tags: ["data", "analysis", "statistics"],
  },
  {
    id: "research-assistant",
    category: "analysis",
    name: "Research Assistant",
    description: "Structured research with source awareness",
    system_prompt: "You are a thorough research assistant. Provide well-organized, factual information. Acknowledge uncertainty and knowledge cutoffs. Suggest reliable sources. Break complex topics into clear explanations.",
    tags: ["research", "facts", "academic"],
  },
  {
    id: "devils-advocate",
    category: "analysis",
    name: "Devil's Advocate",
    description: "Challenge ideas and explore counterarguments",
    system_prompt: "You are a critical thinking partner. For any idea or plan, present thoughtful counterarguments, identify potential flaws, and explore alternative perspectives. Be rigorous but constructive.",
    tags: ["debate", "critical", "thinking"],
  },
  {
    id: "socratic-tutor",
    category: "analysis",
    name: "Socratic Tutor",
    description: "Learn through guided questions, not direct answers",
    system_prompt: "You are a Socratic tutor. Instead of giving direct answers, guide learners to discover insights through carefully crafted questions. Develop their critical thinking and celebrate their discoveries.",
    tags: ["learning", "teaching", "questions"],
  },
  {
    id: "recipe-chef",
    category: "productivity",
    name: "Culinary Guide",
    description: "Recipes, techniques, and meal planning",
    system_prompt: "You are a knowledgeable chef and culinary guide. Help with recipes, cooking techniques, ingredient substitutions, and meal planning. Explain the why behind techniques and consider available equipment.",
    tags: ["cooking", "recipes", "food"],
  },
];
```

- [ ] **Step 2: Create PromptTemplateModal.vue**

Create `frontend/src/components/PromptTemplateModal.vue`:

```vue
<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
    @click.self="$emit('close')"
  >
    <div class="bg-zinc-900 border border-zinc-700 rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl mx-4">
      <div class="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
        <h2 class="text-sm font-semibold text-zinc-100">Prompt Templates</h2>
        <button class="p-1 hover:bg-zinc-800 rounded" @click="$emit('close')">
          <X class="w-4 h-4 text-zinc-400" />
        </button>
      </div>
      <div class="px-5 py-3 border-b border-zinc-800 space-y-3">
        <input
          v-model="search"
          type="text"
          placeholder="Filter templates..."
          class="w-full bg-zinc-800 rounded-md px-3 py-1.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none"
        />
        <div class="flex gap-2 flex-wrap">
          <button
            v-for="cat in CATEGORIES"
            :key="cat"
            :class="[
              'px-2.5 py-1 rounded-md text-xs transition-colors capitalize',
              activeCategory === cat
                ? 'bg-zinc-100 text-zinc-900 font-medium'
                : 'bg-zinc-800 text-zinc-400 hover:text-zinc-100'
            ]"
            @click="activeCategory = cat"
          >
            {{ cat === 'all' ? 'All' : cat }}
          </button>
        </div>
      </div>
      <div class="flex-1 overflow-y-auto p-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div
          v-for="t in filtered"
          :key="t.id"
          class="bg-zinc-800/60 border border-zinc-700/50 rounded-lg p-3 cursor-pointer hover:border-zinc-500 hover:bg-zinc-800 transition-all"
          @click="$emit('select', t)"
        >
          <div class="text-xs font-medium text-zinc-100 mb-1">{{ t.name }}</div>
          <div class="text-[11px] text-zinc-400 mb-2 line-clamp-2">{{ t.description }}</div>
          <div class="flex flex-wrap gap-1">
            <span
              v-for="tag in t.tags.slice(0, 3)"
              :key="tag"
              class="text-[10px] px-1.5 py-0.5 bg-zinc-700 rounded text-zinc-400"
            >{{ tag }}</span>
          </div>
        </div>
        <div v-if="filtered.length === 0" class="col-span-2 text-center py-10 text-xs text-zinc-500">
          No templates match your filter
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { X } from 'lucide-vue-next';
import { PROMPT_TEMPLATES, type PromptTemplate } from '@/data/prompt-templates';

defineEmits<{ close: []; select: [template: PromptTemplate] }>();

const CATEGORIES = ['all', 'coding', 'analysis', 'writing', 'productivity', 'language'] as const;
const search = ref('');
const activeCategory = ref<string>('all');

const filtered = computed(() =>
  PROMPT_TEMPLATES.filter((t) => {
    const catOk = activeCategory.value === 'all' || t.category === activeCategory.value;
    const sq = search.value.toLowerCase();
    const searchOk = !sq ||
      t.name.toLowerCase().includes(sq) ||
      t.description.toLowerCase().includes(sq) ||
      t.tags.some((tag) => tag.includes(sq));
    return catOk && searchOk;
  })
);
</script>
```

- [ ] **Step 3: Integrate into ChatPage.vue**

In `<script setup>` of `ChatPage.vue`, add:

```typescript
import { Sparkles } from 'lucide-vue-next';
import PromptTemplateModal from '@/components/PromptTemplateModal.vue';
import type { PromptTemplate } from '@/data/prompt-templates';
import { patchConversation } from '@/api';

const showTemplates = ref(false);

const applyTemplate = async (template: PromptTemplate) => {
  showTemplates.value = false;
  if (chat.currentConvId) {
    try {
      await patchConversation(chat.currentConvId, {
        persona_override: template.system_prompt,
      });
    } catch { /* ignore */ }
  }
};
```

Add a Sparkles button in the chat input area (next to the existing image/mic buttons):

```html
<button
  class="p-2.5 text-zinc-500 hover:text-white transition-colors"
  title="Prompt Templates"
  @click="showTemplates = true"
>
  <Sparkles class="w-4 h-4" />
</button>
```

Add modal at the end of the template:

```html
<PromptTemplateModal
  v-if="showTemplates"
  @close="showTemplates = false"
  @select="applyTemplate"
/>
```

- [ ] **Step 4: Type-check**

```bash
cd frontend && bun run type-check
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/data/prompt-templates.ts frontend/src/components/PromptTemplateModal.vue frontend/src/pages/ChatPage.vue
git commit -m "feat(frontend): add prompt template library with 20 built-in templates"
```

---

## Task 10: Final Checks + Push

- [ ] **Step 1: Full backend static check**

```bash
cd backend
uv run ruff check --fix
uv run ruff format
uv run mypy app
```

Expected: zero errors

- [ ] **Step 2: FastAPI collection check (catches response_model errors)**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```

Expected: `N tests collected` with no import errors

- [ ] **Step 3: Run all backend tests**

```bash
cd backend && uv run pytest tests/ -v --timeout=30 2>&1 | tail -30
```

Expected: all tests pass

- [ ] **Step 4: Frontend checks**

```bash
cd frontend && bun run lint:fix && bun run type-check
```

Expected: no errors

- [ ] **Step 5: Pre-commit**

```bash
pre-commit run --all-files
```

- [ ] **Step 6: Push**

```bash
git push origin dev
```

---

## Summary

| Task | Files | Commit message |
|------|-------|----------------|
| 1 | migration + models.py | `feat(db): add trigram indexes and source_url` |
| 2 | conversations.py + tests | `feat(api): add conversation search endpoint` |
| 3 | conversations.py + deps.py + tests | `feat(api): add conversation export endpoint` |
| 4 | conversations.py + tests | `feat(api): add PATCH /conversations/{id}` |
| 5A | chat.py | `feat(chat): add image validation` |
| 5B | ChatPage.vue | `feat(frontend): add image paste` |
| 6 | conversations.py + tests + ChatPage.vue | `feat: RAG source citations` |
| 7 | pyproject.toml + documents.py + tests | `feat(api): add URL ingestion` |
| 8 | api/index.ts + ChatPage.vue + DocumentsPage.vue | `feat(frontend): search/export/URL ingestion` |
| 9 | prompt-templates.ts + PromptTemplateModal.vue + ChatPage.vue | `feat(frontend): prompt template library` |
| 10 | — | Final checks + push |
