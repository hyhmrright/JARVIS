# Phase 1: Fix Broken + Multi-tenant DB Predesign — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every existing feature actually work, and pre-design the DB schema for future multi-tenancy.

**Architecture:** Five independent tasks executed in order. Tasks 1.1 and 1.2 share a dependency (RAG context helper is used by Voice), so 1.2 must come before 1.1's final wiring. Tasks 1.3–1.5 are fully independent of 1.1/1.2.

**Tech Stack:** FastAPI, SQLAlchemy async, ARQ, APScheduler, edge-tts, openai (Whisper), Alembic, Vue 3 + Pinia

---

## Chunk 1: Tasks 1.2, 1.1, 1.3

---

### Task 1.2 — RAG Integration in Background Agent Tasks

**Files:**
- Create: `backend/app/rag/context.py`
- Modify: `backend/app/gateway/agent_runner.py`
- Modify: `backend/app/gateway/router.py`
- Modify: `backend/app/api/chat.py`
- Modify: `backend/tests/gateway/test_gateway_rag.py`
- Test: `backend/tests/rag/test_context.py`

#### Background

`rag/retriever.py` has `maybe_inject_rag_context(messages, query, user_id, openai_key) -> list[BaseMessage]` that injects into a message list. But `agent_runner.py` (cron/webhook) never calls it — background tasks have no RAG context. We need a shared text-based helper that works everywhere.

#### Step-by-step

- [ ] **Step 1: Write the failing test for `context.py`**

Create `backend/tests/rag/test_context.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from app.rag.context import build_rag_context


@pytest.mark.asyncio
async def test_build_rag_context_returns_empty_without_key():
    result = await build_rag_context(
        user_id="u1", query="test", openai_key=None
    )
    assert result == ""


@pytest.mark.asyncio
async def test_build_rag_context_returns_empty_when_no_chunks():
    with patch(
        "app.rag.context.retrieve_context",
        new=AsyncMock(return_value=[]),
    ):
        result = await build_rag_context(
            user_id="u1", query="test", openai_key="sk-test"
        )
    assert result == ""


@pytest.mark.asyncio
async def test_build_rag_context_formats_chunks():
    from app.rag.retriever import RetrievedChunk

    chunk = RetrievedChunk(
        document_name="guide.pdf", content="Hello world", score=0.9
    )
    with patch(
        "app.rag.context.retrieve_context",
        new=AsyncMock(return_value=[chunk]),
    ):
        result = await build_rag_context(
            user_id="u1", query="test", openai_key="sk-test"
        )
    assert "guide.pdf" in result
    assert "Hello world" in result
```

- [ ] **Step 2: Run test — expect ImportError (module doesn't exist yet)**

```bash
cd backend && uv run pytest tests/rag/test_context.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.rag.context'`

- [ ] **Step 3: Create `backend/app/rag/context.py`**

**Important:** Import the retriever module (not the function) so that existing tests can keep patching `app.rag.retriever.retrieve_context` and the mock will take effect.

```python
"""Shared RAG context helper for use in any agent execution path."""

import structlog

from app.rag import retriever as _retriever
from app.rag.retriever import RetrievedChunk

logger = structlog.get_logger(__name__)


async def build_rag_context(
    user_id: str,
    query: str,
    openai_key: str | None,
) -> str:
    """Retrieve relevant chunks and return them as a formatted context string.

    Returns empty string when no key is provided, no chunks are found,
    or retrieval fails. Never raises.
    """
    if not openai_key:
        return ""
    try:
        chunks = await _retriever.retrieve_context(query, user_id, openai_key)
        if not chunks:
            return ""
        logger.info(
            "rag_context_built",
            user_id=user_id,
            chunk_count=len(chunks),
        )
        return _format_chunks(chunks)
    except Exception:
        logger.warning("rag_context_build_failed", exc_info=True)
        return ""


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    lines = ["[Knowledge Base Context]"]
    for chunk in chunks:
        lines.append(
            f'Document: "{chunk.document_name}"'
            f" (relevance: {chunk.score:.2f})"
        )
        lines.append(chunk.content)
        lines.append("")
    lines.append(
        "Use the above context to answer the user's question. "
        "Cite document names when referencing this content."
    )
    return "\n".join(lines)
```

- [ ] **Step 4: Run test — expect pass**

```bash
cd backend && uv run pytest tests/rag/test_context.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Wire `build_rag_context` into `agent_runner.py`**

In `backend/app/gateway/agent_runner.py`, add import at top:
```python
from app.rag.context import build_rag_context
from app.core.security import resolve_api_key
```

In `run_agent_for_user()`, after resolving `raw_keys` and before building `lc_messages`, add:

```python
            # RAG: inject relevant context for this task
            openai_key = resolve_api_key("openai", raw_keys)
            rag_context = await build_rag_context(user_id, task, openai_key)
            if rag_context:
                full_task = f"{rag_context}\n\n{full_task}" if ctx_block else f"{rag_context}\n\n{task}"
```

**Note:** `resolve_api_key` is already imported in `agent_runner.py` for the `openai_api_key` parameter passed to `create_graph`. Just add the RAG call.

Actually, simpler — add after `full_task` is computed (after the `ctx_block` prepend):

```python
            # Build full task with optional trigger context prefix
            ctx_block = format_trigger_context(trigger_ctx)
            full_task = f"{ctx_block}\n\n[用户任务]\n{task}" if ctx_block else task

            # RAG: inject relevant knowledge-base context
            openai_key = resolve_api_key("openai", raw_keys)
            rag_context = await build_rag_context(user_id, full_task, openai_key)
            if rag_context:
                full_task = f"{rag_context}\n\n{full_task}"
```

- [ ] **Step 6: Update `router.py` to use `build_rag_context`**

In `backend/app/gateway/router.py`, find where `maybe_inject_rag_context` is called and replace with `build_rag_context`. Add the import at top:
```python
from app.rag.context import build_rag_context
```

Replace the `maybe_inject_rag_context` call with:
```python
rag_context = await build_rag_context(user_id, query, openai_key)
if rag_context:
    lc_messages = [lc_messages[0], SystemMessage(content=rag_context), *lc_messages[1:]]
```
(Remove the `from app.rag.retriever import maybe_inject_rag_context` import.)

- [ ] **Step 7: Update `chat.py` to use `build_rag_context`**

In `backend/app/api/chat.py`, line 30 imports `maybe_inject_rag_context`. Replace:
```python
# Remove this:
from app.rag.retriever import maybe_inject_rag_context
# Add this:
from app.rag.context import build_rag_context
```

Find the call at ~line 271:
```python
lc_messages = await maybe_inject_rag_context(
    lc_messages, rag_query, str(user.id), openai_key
)
```
Replace with:
```python
rag_ctx = await build_rag_context(str(user.id), rag_query, openai_key)
if rag_ctx:
    lc_messages = [
        lc_messages[0],
        SystemMessage(content=rag_ctx),
        *lc_messages[1:],
    ]
```

- [ ] **Step 8: Verify `test_gateway_rag.py` compatibility**

The existing `test_gateway_rag.py` patches `app.rag.retriever.retrieve_context` directly. Because `context.py` accesses `retrieve_context` via module reference (`_retriever.retrieve_context`), patching `app.rag.retriever.retrieve_context` still works — no test changes needed. Confirm by running:

```bash
cd backend && uv run pytest tests/gateway/test_gateway_rag.py -v
```
Expected: all 5 tests PASSED

- [ ] **Step 9: Run ruff + all related tests**

```bash
cd backend
uv run ruff check --fix && uv run ruff format
uv run pytest tests/rag/test_context.py tests/gateway/test_gateway_rag.py tests/gateway/test_gateway_runner.py -v
```
Expected: all PASSED

- [ ] **Step 10: Commit**

```bash
cd backend
git add app/rag/context.py app/gateway/agent_runner.py app/gateway/router.py \
        app/api/chat.py tests/rag/test_context.py
git commit -m "feat: add shared RAG context helper; wire into agent_runner, router, and chat"
```

---

### Task 1.1 — Voice Complete Fix

**Files:**
- Modify: `backend/app/api/voice.py`
- Test: `backend/tests/api/test_voice.py`

#### Background

Current state of `voice.py`:
- No authentication (no `?token=` validation)
- Placeholder STT (`user_text = "Hello, what can you do?"`)
- Hardcoded `provider="deepseek"`, `model="deepseek-chat"`, `user_id="voice-user"`
- Hardcoded TTS voice `zh-CN-XiaoxiaoNeural`

`deps.py` already has `get_current_user_query_token(token: str = Query(...))` for WebSocket auth via `?token=`.

The frontend (`useVoiceStream.ts`) already:
- Connects with `?token=<jwt>` query param
- Sends audio via MediaRecorder (WebM format)
- Handles `transcription`, `ai_text_delta`, `done`, and will handle `error` messages

#### TTS Voice Mapping

| locale param | TTS voice |
|---|---|
| `zh` | `zh-CN-XiaoxiaoNeural` |
| `en` | `en-US-JennyNeural` |
| `ja` | `ja-JP-NanamiNeural` |
| `ko` | `ko-KR-SunHiNeural` |
| `fr` | `fr-FR-DeniseNeural` |
| `de` | `de-DE-KatjaNeural` |
| (default) | `zh-CN-XiaoxiaoNeural` |

- [ ] **Step 1: Write failing tests**

Create `backend/tests/api/test_voice.py`:

```python
"""Tests for voice WebSocket endpoint."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_voice_rejects_missing_token(client):
    """WebSocket connection without token returns 403."""
    with pytest.raises(Exception):
        async with client.websocket_connect("/api/voice/stream") as ws:
            await ws.receive_json()


@pytest.mark.asyncio
async def test_get_tts_voice_mapping():
    """TTS voice is selected based on locale parameter."""
    from app.api.voice import _get_tts_voice

    assert _get_tts_voice("zh") == "zh-CN-XiaoxiaoNeural"
    assert _get_tts_voice("en") == "en-US-JennyNeural"
    assert _get_tts_voice("ja") == "ja-JP-NanamiNeural"
    assert _get_tts_voice("unknown") == "zh-CN-XiaoxiaoNeural"


@pytest.mark.asyncio
async def test_voice_sends_error_on_stt_failure(auth_client, auth_headers):
    """When STT fails, server sends error message and closes."""
    token = auth_headers["Authorization"].split(" ")[1]
    with patch(
        "app.api.voice.transcribe_audio",
        new=AsyncMock(side_effect=Exception("STT failed")),
    ):
        async with auth_client.websocket_connect(
            f"/api/voice/stream?token={token}"
        ) as ws:
            await ws.send_bytes(b"fake audio data")
            msg = await ws.receive_json()
    assert msg["type"] == "error"
```

- [ ] **Step 2: Run tests — expect failures**

```bash
cd backend && uv run pytest tests/api/test_voice.py -v
```
Expected: ImportError or FAILED (functions don't exist yet)

- [ ] **Step 3: Rewrite `backend/app/api/voice.py`**

```python
"""Voice WebSocket: JWT auth + Whisper STT + user LLM settings + edge-TTS."""

import io

import edge_tts
import openai
import structlog
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import create_graph
from app.agent.persona import build_system_prompt
from app.agent.state import AgentState
from app.api.deps import get_current_user_query_token
from app.core.config import settings
from app.core.permissions import DEFAULT_ENABLED_TOOLS
from app.core.security import resolve_api_key, resolve_api_keys
from app.db.models import User, UserSettings
from app.db.session import get_db
from app.rag.context import build_rag_context

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/voice", tags=["voice"])

_TTS_VOICE_MAP: dict[str, str] = {
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-JennyNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
}
_DEFAULT_TTS_VOICE = "zh-CN-XiaoxiaoNeural"


def _get_tts_voice(locale: str) -> str:
    """Return edge-tts voice name for the given locale prefix."""
    return _TTS_VOICE_MAP.get(locale[:2].lower(), _DEFAULT_TTS_VOICE)


async def transcribe_audio(audio_bytes: bytes, openai_key: str) -> str:
    """Call OpenAI Whisper API and return transcript text."""
    client = openai.AsyncOpenAI(api_key=openai_key)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.webm"
    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )
    return transcript.text


@router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    locale: str = Query(default="zh"),
    user: User = Depends(get_current_user_query_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    """WebSocket for real-time voice interaction.

    Protocol:
    - Client connects with ?token=<jwt>[&locale=<zh|en|ja|...>]
    - Client sends binary audio chunks (WebM)
    - Server sends JSON: {"type": "transcription", "text": "..."}
    - Server sends JSON: {"type": "ai_text_delta", "delta": "..."}
    - Server sends binary audio response (MP3 chunks)
    - Server sends JSON: {"type": "done"}
    - Server sends JSON: {"type": "error", "message": "..."} on failure
    """
    await websocket.accept()
    logger.info("voice_websocket_connected", user_id=str(user.id))

    # Load user LLM settings
    us = await db.scalar(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    provider = us.model_provider if us else "deepseek"
    model_name = us.model_name if us else "deepseek-chat"
    raw_keys = us.api_keys if us else {}
    persona = us.persona_override if us else None
    enabled = (
        us.enabled_tools
        if us and us.enabled_tools is not None
        else DEFAULT_ENABLED_TOOLS
    )

    api_keys = resolve_api_keys(provider, raw_keys)
    openai_key = resolve_api_key("openai", raw_keys)
    tts_voice = _get_tts_voice(locale)

    try:
        while True:
            audio_bytes = await websocket.receive_bytes()

            # STT: Whisper
            if not openai_key:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "OpenAI API key required for speech recognition.",
                    }
                )
                continue
            try:
                user_text = await transcribe_audio(audio_bytes, openai_key)
            except Exception as exc:
                logger.warning("voice_stt_failed", error=str(exc))
                await websocket.send_json(
                    {"type": "error", "message": "Speech recognition failed."}
                )
                continue

            await websocket.send_json(
                {"type": "transcription", "text": user_text}
            )

            # RAG context injection
            rag_context = await build_rag_context(
                str(user.id), user_text, openai_key
            )

            from langchain_core.messages import HumanMessage, SystemMessage

            system_content = build_system_prompt(persona)
            if rag_context:
                lc_messages = [
                    SystemMessage(content=system_content),
                    SystemMessage(content=rag_context),
                    HumanMessage(content=user_text),
                ]
            else:
                lc_messages = [
                    SystemMessage(content=system_content),
                    HumanMessage(content=user_text),
                ]

            if not api_keys:
                await websocket.send_json(
                    {"type": "error", "message": "No LLM API key configured."}
                )
                continue

            graph = create_graph(
                provider=provider,
                model=model_name,
                api_key=api_keys[0],
                enabled_tools=enabled,
                api_keys=api_keys,
                user_id=str(user.id),
                openai_api_key=openai_key,
                tavily_api_key=settings.tavily_api_key,
            )

            # Stream LLM response
            full_reply = ""
            async for chunk in graph.astream(
                AgentState(messages=lc_messages)
            ):
                if "llm" in chunk:
                    msg = chunk["llm"]["messages"][-1]
                    if msg.content:
                        delta = str(msg.content)[len(full_reply):]
                        full_reply = str(msg.content)
                        if delta:
                            await websocket.send_json(
                                {"type": "ai_text_delta", "delta": delta}
                            )

            # TTS
            if full_reply:
                communicate = edge_tts.Communicate(full_reply, tts_voice)
                async for tts_chunk in communicate.stream():
                    if (
                        tts_chunk["type"] == "audio"
                        and tts_chunk.get("data")
                    ):
                        await websocket.send_bytes(tts_chunk["data"])

            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        logger.info("voice_websocket_disconnected", user_id=str(user.id))
    except Exception:
        logger.exception("voice_websocket_error", user_id=str(user.id))
        try:
            await websocket.send_json(
                {"type": "error", "message": "Internal server error."}
            )
        except Exception:
            pass
```

- [ ] **Step 4: Run lint and import check**

```bash
cd backend
uv run ruff check --fix && uv run ruff format
uv run pytest --collect-only -q 2>&1 | head -20
```
Expected: no collection errors

- [ ] **Step 5: Run voice tests**

```bash
cd backend && uv run pytest tests/api/test_voice.py -v
```
Expected: `test_get_tts_voice_mapping` PASSED.

For `test_voice_rejects_missing_token` and `test_voice_sends_error_on_stt_failure`: these use the `client` / `auth_client` fixtures from `conftest.py`. The `httpx.AsyncClient` with `ASGITransport` supports WebSocket connections via `.websocket_connect()`. These tests should pass with the existing fixture infrastructure.

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/api/voice.py tests/api/test_voice.py
git commit -m "feat: rewrite voice WebSocket with JWT auth, Whisper STT, user LLM settings, locale TTS"
```

---

### Task 1.3 — Multi-tenant DB Predesign

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/013_multi_tenant_predesign.py`
- Test: `backend/tests/db/test_multi_tenant_models.py`

#### Background

Add `Organization` and `Workspace` models (no business logic yet — just the tables). Add nullable `organization_id` / `workspace_id` columns to existing tables so future migrations can activate multi-tenancy with minimal schema changes.

#### Step-by-step

- [ ] **Step 1: Write the failing test**

Create `backend/tests/db/test_multi_tenant_models.py`:

```python
"""Verify Organization and Workspace models are importable and column names are correct."""

from app.db.models import Organization, User, Workspace


def test_organization_model_has_required_columns():
    cols = {c.name for c in Organization.__table__.columns}
    assert "id" in cols
    assert "name" in cols
    assert "slug" in cols
    assert "owner_id" in cols
    assert "created_at" in cols


def test_workspace_model_has_required_columns():
    cols = {c.name for c in Workspace.__table__.columns}
    assert "id" in cols
    assert "name" in cols
    assert "organization_id" in cols
    assert "created_at" in cols


def test_user_has_organization_id_column():
    cols = {c.name for c in User.__table__.columns}
    assert "organization_id" in cols
```

- [ ] **Step 2: Run test — expect ImportError**

```bash
cd backend && uv run pytest tests/db/test_multi_tenant_models.py -v
```
Expected: `ImportError: cannot import name 'Organization'`

- [ ] **Step 3: Add models to `backend/app/db/models.py`**

Add at the end of the file (after `ApiKey`):

```python
class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

Also add nullable columns to existing models. In `User`:
```python
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
```
In `Conversation`:
```python
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
```
In `Document`:
```python
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
```
In `CronJob`:
```python
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
```
In `Webhook`:
```python
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
```

- [ ] **Step 4: Run test — expect pass**

```bash
cd backend && uv run pytest tests/db/test_multi_tenant_models.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Create Alembic migration**

Create `backend/alembic/versions/013_multi_tenant_predesign.py`:

```python
"""Multi-tenant DB predesign: add organizations/workspaces tables and nullable FK columns.

Revision ID: 013
Revises: 012
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create organizations table
    op.create_table(
        "organizations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_organizations_owner_id", "organizations", ["owner_id"])

    # Create workspaces table
    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_workspaces_organization_id", "workspaces", ["organization_id"]
    )

    # Add nullable columns to existing tables
    op.add_column(
        "users",
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.create_index(
        "ix_users_organization_id", "users", ["organization_id"]
    )

    for table in ("conversations", "documents", "cron_jobs", "webhooks"):
        op.add_column(
            table,
            sa.Column(
                "workspace_id", postgresql.UUID(as_uuid=True), nullable=True
            ),
        )
        op.create_index(
            f"ix_{table}_workspace_id", table, ["workspace_id"]
        )


def downgrade() -> None:
    for table in ("conversations", "documents", "cron_jobs", "webhooks"):
        op.drop_index(f"ix_{table}_workspace_id", table_name=table)
        op.drop_column(table, "workspace_id")

    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_column("users", "organization_id")

    op.drop_index("ix_workspaces_organization_id", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index("ix_organizations_owner_id", table_name="organizations")
    op.drop_table("organizations")
```

- [ ] **Step 6: Run lint + import check**

```bash
cd backend
uv run ruff check --fix && uv run ruff format
uv run pytest --collect-only -q 2>&1 | head -20
```
Expected: no errors

- [ ] **Step 7: Commit**

```bash
cd backend
git add app/db/models.py \
        alembic/versions/013_multi_tenant_predesign.py \
        tests/db/test_multi_tenant_models.py
git commit -m "feat: add Organization/Workspace models and multi-tenant predesign migration 013"
```

---

## Chunk 2: Tasks 1.4, 1.5

---

### Task 1.4 — Cron Small Fixes ✅ COMPLETED

**Files:**
- Create: `backend/app/scheduler/trigger_schemas.py`
- Modify: `backend/app/api/cron.py`
- Modify: `backend/app/scheduler/runner.py`
- Modify: `backend/app/api/documents.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/scheduler/test_trigger_schemas.py`

#### Background

Four independent fixes:
1. **`next_run_at`**: After creating or toggling a job active, read `next_run_time` from APScheduler and write to `cron_jobs.next_run_at`
2. **`chunk_count = 0` on document delete**: Currently, `Document.chunk_count` stays stale after soft-deletion. Reset it.
3. **`CRON_LOCK_TTL_SECONDS`** config setting (currently hardcoded as `_LOCK_TTL_SECONDS = 300` in `worker.py`)
4. **Trigger metadata validation** via Pydantic models + `PUT /api/cron/{id}` endpoint

#### Step-by-step

- [ ] **Step 1: Write failing tests for trigger_schemas**

Create `backend/tests/scheduler/test_trigger_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.scheduler.trigger_schemas import (
    EmailWatcherMetadata,
    SemanticWatcherMetadata,
    WebWatcherMetadata,
    validate_trigger_metadata,
)


def test_web_watcher_requires_url():
    with pytest.raises(ValidationError):
        WebWatcherMetadata(**{})


def test_web_watcher_valid():
    m = WebWatcherMetadata(url="https://example.com")
    assert str(m.url).startswith("https://")


def test_semantic_watcher_requires_url_and_target():
    with pytest.raises(ValidationError):
        SemanticWatcherMetadata(url="https://example.com")  # missing target
    with pytest.raises(ValidationError):
        SemanticWatcherMetadata(target="price")  # missing url


def test_email_watcher_requires_host_and_address():
    with pytest.raises(ValidationError):
        EmailWatcherMetadata(imap_host="imap.gmail.com")  # missing email_address


def test_validate_trigger_metadata_unknown_type_passes():
    # cron type has no metadata requirements
    result = validate_trigger_metadata("cron", {})
    assert result is None  # returns None, no error


def test_validate_trigger_metadata_invalid_raises():
    with pytest.raises(ValidationError):
        validate_trigger_metadata("web_watcher", {})
```

- [ ] **Step 2: Run test — expect ImportError**

```bash
cd backend && uv run pytest tests/scheduler/test_trigger_schemas.py -v
```
Expected: ImportError

- [ ] **Step 3: Create `backend/app/scheduler/trigger_schemas.py`**

```python
"""Pydantic validation schemas for trigger metadata by trigger type."""

from pydantic import BaseModel, HttpUrl


class WebWatcherMetadata(BaseModel):
    url: HttpUrl
    last_hash: str | None = None


class SemanticWatcherMetadata(BaseModel):
    url: HttpUrl
    target: str
    fire_on_init: bool = False
    content_hash: str | None = None
    last_semantic_summary: str | None = None


class EmailWatcherMetadata(BaseModel):
    imap_host: str
    email_address: str
    imap_password: str | None = None
    imap_port: int = 993
    imap_folder: str = "INBOX"


_SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "web_watcher": WebWatcherMetadata,
    "semantic_watcher": SemanticWatcherMetadata,
    "email": EmailWatcherMetadata,
}


def validate_trigger_metadata(
    trigger_type: str, metadata: dict
) -> BaseModel | None:
    """Validate metadata dict against the schema for trigger_type.

    Returns the validated model, or None for types with no schema.
    Raises ValidationError on invalid metadata.
    """
    schema = _SCHEMA_MAP.get(trigger_type)
    if schema is None:
        return None
    return schema(**metadata)
```

- [ ] **Step 4: Run test — expect pass**

```bash
cd backend && uv run pytest tests/scheduler/test_trigger_schemas.py -v
```
Expected: 6 PASSED

- [ ] **Step 5: Wire validation into `POST /api/cron` and add `PUT /api/cron/{id}`**

In `backend/app/api/cron.py`:

Add import:
```python
from app.scheduler.trigger_schemas import validate_trigger_metadata
```

Add `CronJobUpdate` schema after `CronJobCreate`:
```python
class CronJobUpdate(BaseModel):
    schedule: str | None = Field(default=None, min_length=1, max_length=100)
    task: str | None = Field(default=None, min_length=1, max_length=4000)
    trigger_metadata: dict[str, Any] | None = None
```

In `create_cron_job`, after the quota check, add validation:
```python
    # Validate trigger metadata
    try:
        validate_trigger_metadata(
            data.trigger_type, data.trigger_metadata or {}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid trigger_metadata: {exc}",
        ) from exc
```

Add `PUT` endpoint after the `PATCH toggle` endpoint:
```python
@router.put("/{job_id}")
async def update_cron_job(
    job_id: uuid.UUID,
    data: CronJobUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update schedule, task, or trigger_metadata of an existing job."""
    job = await db.get(CronJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    if data.trigger_metadata is not None:
        try:
            validate_trigger_metadata(
                job.trigger_type, data.trigger_metadata
            )
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid trigger_metadata: {exc}",
            ) from exc

    if data.schedule is not None:
        job.schedule = data.schedule
    if data.task is not None:
        job.task = data.task
    if data.trigger_metadata is not None:
        job.trigger_metadata = data.trigger_metadata

    await db.commit()

    if job.is_active:
        unregister_cron_job(str(job.id))
        register_cron_job(str(job.id), job.schedule)

    return {"status": "ok", "id": str(job.id)}
```

- [ ] **Step 6: Fix `next_run_at` — update `register_cron_job` in `runner.py`**

In `backend/app/scheduler/runner.py`, update `register_cron_job` to return the next run time:

```python
from datetime import datetime


def register_cron_job(job_id: str, schedule: str) -> datetime | None:
    """Register a single cron job with the scheduler. Returns next run time."""
    scheduler = get_scheduler()
    job_key = f"cron_{job_id}"
    if scheduler.get_job(job_key):
        scheduler.remove_job(job_key)
    apscheduler_job = scheduler.add_job(
        _execute_cron_job,
        trigger=CronTrigger.from_crontab(schedule),
        id=job_key,
        kwargs={"job_id": job_id},
        misfire_grace_time=60,
        coalesce=True,
    )
    return apscheduler_job.next_run_time
```

In `backend/app/api/cron.py`, update `create_cron_job` to write `next_run_at`:

```python
    # Register with live scheduler
    if job.is_active:
        next_run_time = register_cron_job(str(job.id), job.schedule)
        if next_run_time:
            job.next_run_at = next_run_time
            await db.commit()
```

Also update `toggle_cron_job` to write `next_run_at`:
```python
    if job.is_active:
        next_run_time = register_cron_job(str(job.id), job.schedule)
        if next_run_time:
            job.next_run_at = next_run_time
            await db.commit()
    else:
        unregister_cron_job(str(job.id))
        job.next_run_at = None
        await db.commit()
```

Also include `next_run_at` in the list response in `list_cron_jobs`:
```python
"next_run_at": j.next_run_at.isoformat() if j.next_run_at else None,
```

- [ ] **Step 7: Fix `chunk_count = 0` on document delete**

In `backend/app/api/documents.py`, in `delete_document`, after `doc.is_deleted = True`:

```python
    doc.is_deleted = True
    doc.chunk_count = 0
    await db.commit()
```

- [ ] **Step 8: Add `CRON_LOCK_TTL_SECONDS` to config**

In `backend/app/core/config.py`, add to `Settings`:
```python
    cron_lock_ttl_seconds: int = 300
```

In `backend/app/worker.py`, replace hardcoded constant:
```python
# Remove: _LOCK_TTL_SECONDS = 300
# Replace usage with: settings.cron_lock_ttl_seconds
```

The line `acquired = await redis.set(lock_key, 1, nx=True, ex=_LOCK_TTL_SECONDS)` becomes:
```python
acquired = await redis.set(
    lock_key, 1, nx=True, ex=settings.cron_lock_ttl_seconds
)
```

- [ ] **Step 9: Add tests for PUT endpoint and `next_run_at`**

In `backend/tests/api/test_cron_v2.py`, add:

```python
@pytest.mark.asyncio
async def test_put_cron_job_updates_task(client: AsyncClient, auth_headers: dict):
    """PUT /api/cron/{id} updates task text for owned job."""
    # Create a job first
    create_resp = await client.post(
        "/api/cron",
        json={
            "schedule": "0 9 * * *",
            "task": "original task",
            "trigger_type": "cron",
            "trigger_metadata": {},
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/cron/{job_id}",
        json={"task": "updated task"},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["id"] == job_id


@pytest.mark.asyncio
async def test_put_cron_job_404_for_other_user(
    client: AsyncClient, auth_headers: dict
):
    """PUT /api/cron/{id} returns 404 for unowned job."""
    other_job_id = str(uuid.uuid4())
    resp = await client.put(
        f"/api/cron/{other_job_id}",
        json={"task": "new task"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_job_returns_next_run_at_in_list(
    client: AsyncClient, auth_headers: dict
):
    """After creating a job, list endpoint includes next_run_at."""
    await client.post(
        "/api/cron",
        json={
            "schedule": "0 9 * * *",
            "task": "test task",
            "trigger_type": "cron",
            "trigger_metadata": {},
        },
        headers=auth_headers,
    )
    list_resp = await client.get("/api/cron", headers=auth_headers)
    assert list_resp.status_code == 200
    jobs = list_resp.json()
    assert len(jobs) >= 1
    # next_run_at key must exist (may be None if scheduler not running in test)
    assert "next_run_at" in jobs[0]
```

- [ ] **Step 10: Run lint + tests**

```bash
cd backend
uv run ruff check --fix && uv run ruff format
uv run pytest tests/scheduler/test_trigger_schemas.py tests/api/test_cron_v2.py -v
uv run pytest --collect-only -q 2>&1 | head -20
```
Expected: all PASSED, no collection errors

- [ ] **Step 11: Commit**

```bash
cd backend
git add app/scheduler/trigger_schemas.py app/api/cron.py \
        app/scheduler/runner.py app/api/documents.py app/core/config.py \
        app/worker.py tests/scheduler/test_trigger_schemas.py \
        tests/api/test_cron_v2.py
git commit -m "feat: trigger metadata validation, PUT cron endpoint, next_run_at, chunk_count reset, lock TTL config"
```

---

### Task 1.5 — JobExecution Data Retention

**Files:**
- Modify: `backend/app/worker.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_worker.py`

#### Background

`job_executions` rows accumulate indefinitely. ARQ supports periodic `cron` functions in `WorkerSettings`. We add a daily cleanup task.

#### Step-by-step

- [ ] **Step 1: Read existing `test_worker.py` to understand what's tested**

Read `backend/tests/test_worker.py` to understand existing test structure before adding new tests.

- [ ] **Step 2: Write failing test for cleanup function**

In `backend/tests/test_worker.py`, add:

```python
@pytest.mark.asyncio
async def test_cleanup_old_executions_deletes_old_rows():
    """cleanup_old_executions deletes rows older than retention days."""
    from unittest.mock import AsyncMock, patch, MagicMock
    from app.worker import cleanup_old_executions

    mock_result = MagicMock()
    mock_result.rowcount = 5

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch(
        "app.worker.AsyncSessionLocal",
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_db),
            __aexit__=AsyncMock(return_value=None),
        ),
    ):
        await cleanup_old_executions({})

    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()
```

- [ ] **Step 3: Run test — expect ImportError**

```bash
cd backend && uv run pytest tests/test_worker.py::test_cleanup_old_executions_deletes_old_rows -v
```
Expected: ImportError or AttributeError

- [ ] **Step 4: Add `CRON_EXECUTION_RETENTION_DAYS` to config**

In `backend/app/core/config.py`:
```python
    cron_execution_retention_days: int = 90
```

- [ ] **Step 5: Add `cleanup_old_executions` to `worker.py`**

In `backend/app/worker.py`, add import:
```python
from datetime import timedelta

from sqlalchemy import delete, text
```

Add the function before `WorkerSettings`:

```python
async def cleanup_old_executions(ctx: dict) -> None:
    """ARQ periodic task: delete job_executions older than retention window."""
    cutoff = datetime.now(tz=UTC) - timedelta(
        days=settings.cron_execution_retention_days
    )
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(JobExecution).where(JobExecution.fired_at < cutoff)
        )
        await db.commit()
    logger.info(
        "job_executions_cleanup",
        deleted=result.rowcount,
        retention_days=settings.cron_execution_retention_days,
    )
```

- [ ] **Step 6: Register as ARQ cron task in `WorkerSettings`**

Update `WorkerSettings`:
```python
from arq.cron import cron


class WorkerSettings:
    functions = [execute_cron_job]
    cron_jobs = [
        cron(cleanup_old_executions, hour=3, minute=0)  # Daily 03:00 UTC
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300
    retry_jobs = True
    max_tries = 3
```

- [ ] **Step 7: Run lint + tests**

```bash
cd backend
uv run ruff check --fix && uv run ruff format
uv run pytest tests/test_worker.py -v
uv run pytest --collect-only -q 2>&1 | head -20
```
Expected: all PASSED

- [ ] **Step 8: Commit**

```bash
cd backend
git add app/worker.py app/core/config.py tests/test_worker.py
git commit -m "feat: add JobExecution data retention with configurable CRON_EXECUTION_RETENTION_DAYS"
```

---

## Final Verification

- [ ] **Run full test suite**

```bash
cd backend
uv run ruff check && uv run ruff format --check
uv run mypy app
uv run pytest --collect-only -q
```
Expected: no errors

- [ ] **Push all commits**

```bash
git push origin dev
```
