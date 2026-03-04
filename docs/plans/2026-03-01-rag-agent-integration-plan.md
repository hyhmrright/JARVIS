# Phase 5: RAG × Agent Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire the RAG pipeline into every agent conversation so users get automatic context injection from their knowledge base, plus an on-demand search tool with source citations.

**Architecture:** The existing `rag_tool.py` and `graph.py` wiring already provide the on-demand `rag_search` tool. What's missing is (1) a proper retriever that returns document names + similarity scores, (2) auto-injection of retrieved context as a SystemMessage before the agent runs, and (3) document names stored in Qdrant payloads at index time.

**Tech Stack:** FastAPI, LangGraph, Qdrant (qdrant-client), LangChain (OpenAIEmbeddings), SQLAlchemy async, pytest-asyncio.

**Working directory for all commands:** `backend/`

---

## Task 5.1: Enhanced Retriever Module

**Files:**
- Create: `backend/app/rag/retriever.py`
- Create: `backend/tests/rag/test_retriever.py`

**Context:** `app/rag/indexer.py:36-47` has `search_documents()` that returns `list[str]` with no scores or document names. We need a new retriever that returns structured results with score filtering.

---

**Step 1: Write the failing tests**

Create `backend/tests/rag/test_retriever.py`:

```python
"""Unit tests for the RAG retriever module."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.retriever import RetrievedChunk, retrieve_context


def _make_qdrant_hit(score: float, text: str, doc_name: str = "test.pdf") -> MagicMock:
    hit = MagicMock()
    hit.score = score
    hit.payload = {"text": text, "doc_name": doc_name}
    return hit


@pytest.mark.asyncio
async def test_retrieve_context_returns_chunks_above_threshold() -> None:
    """Should return only chunks with score >= threshold."""
    hits = [
        _make_qdrant_hit(0.85, "relevant content", "doc_a.pdf"),
        _make_qdrant_hit(0.60, "low relevance", "doc_b.pdf"),  # below threshold
    ]
    mock_client = AsyncMock()
    mock_client.search.return_value = hits

    with (
        patch("app.rag.retriever.get_qdrant_client", return_value=mock_client),
        patch(
            "app.rag.retriever.get_embedder"
        ) as mock_embedder_factory,
    ):
        mock_embedder = AsyncMock()
        mock_embedder.aembed_query.return_value = [0.1] * 1536
        mock_embedder_factory.return_value = mock_embedder

        results = await retrieve_context("test query", "user-1", "openai-key")

    assert len(results) == 1
    assert results[0].document_name == "doc_a.pdf"
    assert results[0].content == "relevant content"
    assert results[0].score == 0.85


@pytest.mark.asyncio
async def test_retrieve_context_returns_empty_on_404() -> None:
    """Should return [] if the user has no Qdrant collection (404)."""
    from qdrant_client.http.exceptions import UnexpectedResponse

    mock_client = AsyncMock()
    mock_client.search.side_effect = UnexpectedResponse(
        status_code=404, reason_phrase="Not Found", content=b"", headers={}
    )

    with (
        patch("app.rag.retriever.get_qdrant_client", return_value=mock_client),
        patch(
            "app.rag.retriever.get_embedder"
        ) as mock_embedder_factory,
    ):
        mock_embedder = AsyncMock()
        mock_embedder.aembed_query.return_value = [0.1] * 1536
        mock_embedder_factory.return_value = mock_embedder

        results = await retrieve_context("query", "user-1", "openai-key")

    assert results == []


@pytest.mark.asyncio
async def test_retrieve_context_returns_empty_on_general_error() -> None:
    """Should return [] (not raise) on unexpected Qdrant errors."""
    mock_client = AsyncMock()
    mock_client.search.side_effect = RuntimeError("connection failed")

    with (
        patch("app.rag.retriever.get_qdrant_client", return_value=mock_client),
        patch(
            "app.rag.retriever.get_embedder"
        ) as mock_embedder_factory,
    ):
        mock_embedder = AsyncMock()
        mock_embedder.aembed_query.return_value = [0.1] * 1536
        mock_embedder_factory.return_value = mock_embedder

        results = await retrieve_context("query", "user-1", "openai-key")

    assert results == []


@pytest.mark.asyncio
async def test_retrieve_context_falls_back_doc_name_when_missing() -> None:
    """Should use 'Unknown document' when doc_name absent from payload."""
    hit = MagicMock()
    hit.score = 0.9
    hit.payload = {"text": "some content"}  # no doc_name key

    mock_client = AsyncMock()
    mock_client.search.return_value = [hit]

    with (
        patch("app.rag.retriever.get_qdrant_client", return_value=mock_client),
        patch(
            "app.rag.retriever.get_embedder"
        ) as mock_embedder_factory,
    ):
        mock_embedder = AsyncMock()
        mock_embedder.aembed_query.return_value = [0.1] * 1536
        mock_embedder_factory.return_value = mock_embedder

        results = await retrieve_context("query", "user-1", "openai-key")

    assert results[0].document_name == "Unknown document"
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/rag/test_retriever.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.rag.retriever'`

**Step 3: Implement `app/rag/retriever.py`**

```python
"""Retriever for RAG context injection into the agent conversation."""

from dataclasses import dataclass

import structlog
from qdrant_client.http.exceptions import UnexpectedResponse

from app.infra.qdrant import get_qdrant_client, user_collection_name
from app.rag.embedder import get_embedder

logger = structlog.get_logger(__name__)

_DEFAULT_TOP_K = 5
_DEFAULT_SCORE_THRESHOLD = 0.7


@dataclass
class RetrievedChunk:
    document_name: str
    content: str
    score: float


async def retrieve_context(
    query: str,
    user_id: str,
    openai_api_key: str,
    top_k: int = _DEFAULT_TOP_K,
    score_threshold: float = _DEFAULT_SCORE_THRESHOLD,
) -> list[RetrievedChunk]:
    """Search the user's Qdrant collection and return relevant chunks.

    Returns an empty list (never raises) when the collection does not
    exist, when no chunks exceed the threshold, or on unexpected errors.
    """
    try:
        client = await get_qdrant_client()
        embedder = get_embedder(openai_api_key)
        query_vec = await embedder.aembed_query(query)
        hits = await client.search(
            collection_name=user_collection_name(user_id),
            query_vector=query_vec,
            limit=top_k,
        )
    except UnexpectedResponse as exc:
        if exc.status_code == 404:
            return []
        logger.warning("retriever_qdrant_error", user_id=user_id, error=str(exc))
        return []
    except Exception:
        logger.warning("retriever_unexpected_error", user_id=user_id, exc_info=True)
        return []

    return [
        RetrievedChunk(
            document_name=hit.payload.get("doc_name", "Unknown document"),
            content=hit.payload.get("text", ""),
            score=hit.score,
        )
        for hit in hits
        if hit.score >= score_threshold and hit.payload
    ]
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/rag/test_retriever.py -v
```

Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add app/rag/retriever.py tests/rag/test_retriever.py
git commit -m "feat: add RAG retriever with score filtering and document names"
```

---

## Task 5.2: Store Document Name in Qdrant at Index Time

**Files:**
- Modify: `backend/app/rag/indexer.py` — add `doc_name` param to `index_document()`
- Modify: `backend/app/api/documents.py:90` — pass `doc_name` to `index_document()`

**Context:** Qdrant payloads currently store `{"doc_id", "chunk_index", "text"}`. We add `"doc_name"` so the retriever can show filenames without a DB lookup. Old documents without this field fall back to "Unknown document" (handled in Task 5.1).

---

**Step 1: Write the failing test** (extend existing `tests/rag/test_indexer.py` if it exists, or inline)

Add to `backend/tests/rag/test_retriever.py`:

```python
@pytest.mark.asyncio
async def test_index_document_stores_doc_name_in_payload() -> None:
    """index_document should store doc_name in each Qdrant point's payload."""
    from unittest.mock import call, patch

    from app.rag.indexer import index_document

    captured_points: list = []

    async def fake_upsert(collection_name: str, points: list) -> None:
        captured_points.extend(points)

    mock_client = AsyncMock()
    mock_client.upsert = fake_upsert

    with (
        patch("app.rag.indexer.get_qdrant_client", return_value=mock_client),
        patch("app.rag.indexer.ensure_user_collection"),
        patch("app.rag.indexer.get_embedder") as mock_ef,
    ):
        mock_emb = AsyncMock()
        mock_emb.aembed_documents.return_value = [[0.1] * 1536]
        mock_ef.return_value = mock_emb

        await index_document(
            user_id="u1",
            doc_id="d1",
            text="hello world",
            api_key="key",
            doc_name="report.pdf",
        )

    assert all(p.payload.get("doc_name") == "report.pdf" for p in captured_points)
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/rag/test_retriever.py::test_index_document_stores_doc_name_in_payload -v
```

Expected: FAIL — `index_document()` does not accept `doc_name` keyword.

**Step 3: Modify `app/rag/indexer.py`**

Change the signature and payload of `index_document`:

```python
async def index_document(
    user_id: str,
    doc_id: str,
    text: str,
    api_key: str,
    doc_name: str = "",
) -> int:
    """将文档切片、向量化并写入 Qdrant。返回切片数量。"""
    await ensure_user_collection(user_id)
    client = await get_qdrant_client()
    collection = user_collection_name(user_id)

    chunks = chunk_text(text)
    embedder = get_embedder(api_key)
    vectors = await embedder.aembed_documents(chunks)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={
                "doc_id": doc_id,
                "chunk_index": i,
                "text": chunk,
                "doc_name": doc_name,
            },
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors, strict=True))
    ]
    await client.upsert(collection_name=collection, points=points)
    return len(chunks)
```

**Step 4: Modify `app/api/documents.py` line 90**

Change the `index_document` call to pass the filename:

```python
chunk_count = await index_document(
    str(user.id), str(doc.id), text, openai_key, doc_name=safe_name
)
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/rag/test_retriever.py -v
```

Expected: all 5 tests PASS

**Step 6: Commit**

```bash
git add app/rag/indexer.py app/api/documents.py tests/rag/test_retriever.py
git commit -m "feat: store document name in Qdrant payload at index time"
```

---

## Task 5.3: Update RAG Tool to Use Enhanced Retriever

**Files:**
- Modify: `backend/app/tools/rag_tool.py`
- Create: `backend/tests/tools/test_rag_tool.py`

**Context:** Current `rag_tool.py` calls `search_documents()` which returns `list[str]` with no names. We replace it with `retrieve_context()` from Task 5.1, returning formatted results with document names and scores.

---

**Step 1: Write the failing tests**

Create `backend/tests/tools/test_rag_tool.py`:

```python
"""Unit tests for the RAG search tool."""

from unittest.mock import AsyncMock, patch

import pytest

from app.rag.retriever import RetrievedChunk
from app.tools.rag_tool import create_rag_search_tool


@pytest.mark.asyncio
async def test_rag_tool_formats_results_with_document_names() -> None:
    """Tool output should include document names and relevance scores."""
    chunks = [
        RetrievedChunk("report.pdf", "Key finding here", 0.91),
        RetrievedChunk("FAQ.md", "Common question answer", 0.75),
    ]
    tool = create_rag_search_tool("user-1", "openai-key")

    with patch("app.tools.rag_tool.retrieve_context", return_value=chunks):
        result = await tool.ainvoke({"query": "findings"})

    assert "report.pdf" in result
    assert "0.91" in result
    assert "Key finding here" in result
    assert "FAQ.md" in result


@pytest.mark.asyncio
async def test_rag_tool_returns_no_results_message_when_empty() -> None:
    """Tool should return a helpful message when no documents match."""
    tool = create_rag_search_tool("user-1", "openai-key")

    with patch("app.tools.rag_tool.retrieve_context", return_value=[]):
        result = await tool.ainvoke({"query": "nothing"})

    assert "No relevant" in result


@pytest.mark.asyncio
async def test_rag_tool_handles_retriever_exception() -> None:
    """Tool should return error message when retriever raises."""
    tool = create_rag_search_tool("user-1", "openai-key")

    with patch(
        "app.tools.rag_tool.retrieve_context", side_effect=RuntimeError("boom")
    ):
        result = await tool.ainvoke({"query": "query"})

    assert "Error" in result or "failed" in result.lower()
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/tools/test_rag_tool.py -v
```

Expected: FAIL (import error or assertion error — tool still uses `search_documents`)

**Step 3: Rewrite `app/tools/rag_tool.py`**

```python
"""RAG knowledge base search tool for the LangGraph agent."""

import structlog
from langchain_core.tools import BaseTool, tool

from app.rag.retriever import retrieve_context

logger = structlog.get_logger(__name__)


def create_rag_search_tool(user_id: str, openai_api_key: str) -> BaseTool:
    """Factory that returns a RAG search tool closed over user context."""

    @tool
    async def rag_search(query: str) -> str:
        """Search the user's uploaded knowledge base documents.

        Use this when the user asks about content from their uploaded files
        or documents. query is a natural language search phrase.
        """
        try:
            chunks = await retrieve_context(user_id, query, openai_api_key)
        except Exception:
            logger.exception("rag_search_error", user_id=user_id)
            return "Error: failed to search the knowledge base."

        if not chunks:
            return "No relevant documents found in the knowledge base."

        parts = [
            f"[{i + 1}] Document: \"{c.document_name}\" (relevance: {c.score:.2f})\n{c.content}"
            for i, c in enumerate(chunks)
        ]
        return "\n\n".join(parts)

    return rag_search
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/tools/test_rag_tool.py -v
```

Expected: 3 tests PASS

**Step 5: Commit**

```bash
git add app/tools/rag_tool.py tests/tools/test_rag_tool.py
git commit -m "feat: update RAG tool to use enhanced retriever with document names"
```

---

## Task 5.4: Auto-Inject RAG Context in Web Chat

**Files:**
- Modify: `backend/app/api/chat.py`
- Create: `backend/tests/api/test_chat_rag.py`

**Context:** `chat.py:108-115` builds `lc_messages` from DB history and prepends `system_msg`. We add auto-retrieval here (before `generate()` is returned) and insert a `SystemMessage` with retrieved context at position 1 (right after the persona system message).

---

**Step 1: Write the failing test**

Create `backend/tests/api/test_chat_rag.py`:

```python
"""Tests for auto-RAG context injection in the chat stream endpoint."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.rag.retriever import RetrievedChunk


@pytest.mark.asyncio
async def test_chat_stream_injects_rag_context_when_results_found(
    client: AsyncClient,
    auth_headers: dict,
    conversation_id: uuid.UUID,
) -> None:
    """When retrieve_context returns chunks, a RAG SystemMessage should be injected."""
    chunks = [RetrievedChunk("doc.pdf", "Some relevant content", 0.88)]

    captured_messages: list = []

    async def fake_stream(state, **kw):
        captured_messages.extend(state.messages)
        yield {"llm": {"messages": [MagicMock(content="answer", tool_calls=[])]}}

    with (
        patch(
            "app.api.chat.retrieve_context", new_callable=AsyncMock, return_value=chunks
        ),
        patch("app.api.chat.create_graph") as mock_graph,
    ):
        mock_graph.return_value.astream = fake_stream
        resp = await client.post(
            "/api/chat/stream",
            json={"conversation_id": str(conversation_id), "content": "tell me about doc"},
            headers=auth_headers,
        )

    # Check that a [Knowledge Base Context] message was injected
    context_msgs = [
        m for m in captured_messages if hasattr(m, "content") and "[Knowledge Base Context]" in str(m.content)
    ]
    assert len(context_msgs) == 1
    assert "doc.pdf" in context_msgs[0].content


@pytest.mark.asyncio
async def test_chat_stream_skips_injection_when_no_rag_results(
    client: AsyncClient,
    auth_headers: dict,
    conversation_id: uuid.UUID,
) -> None:
    """When retrieve_context returns [], no RAG message should be injected."""
    captured_messages: list = []

    async def fake_stream(state, **kw):
        captured_messages.extend(state.messages)
        yield {"llm": {"messages": [MagicMock(content="answer", tool_calls=[])]}}

    with (
        patch(
            "app.api.chat.retrieve_context", new_callable=AsyncMock, return_value=[]
        ),
        patch("app.api.chat.create_graph") as mock_graph,
    ):
        mock_graph.return_value.astream = fake_stream
        await client.post(
            "/api/chat/stream",
            json={"conversation_id": str(conversation_id), "content": "hi"},
            headers=auth_headers,
        )

    context_msgs = [
        m for m in captured_messages if "[Knowledge Base Context]" in str(getattr(m, "content", ""))
    ]
    assert len(context_msgs) == 0
```

**Step 2: Check conftest.py for fixtures**

```bash
cat tests/conftest.py
```

If `client`, `auth_headers`, `conversation_id` fixtures are missing, use simpler unit-style approach (see Step 3 note).

**Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/api/test_chat_rag.py -v
```

Expected: FAIL (import error — `retrieve_context` not imported in `chat.py`)

**Step 4: Modify `app/api/chat.py`**

Add import at top of file (after existing imports):

```python
from app.rag.retriever import retrieve_context
```

Add helper function before the `chat_stream` handler:

```python
def _format_rag_context(chunks: list) -> str:
    """Format retrieved chunks into a context block for the system message."""
    lines = ["[Knowledge Base Context]"]
    for chunk in chunks:
        lines.append(
            f'Document: "{chunk.document_name}" (relevance: {chunk.score:.2f})'
        )
        lines.append(chunk.content)
        lines.append("")
    lines.append(
        "Use the above context to answer the user's question. "
        "Cite document names when referencing this content."
    )
    return "\n".join(lines)
```

In `chat_stream()`, after building `lc_messages` (line ~115, after `lc_messages = [system_msg, *lc_messages]`), add:

```python
    # Auto-inject RAG context if user has relevant documents
    if openai_key:
        try:
            rag_chunks = await retrieve_context(
                body.content, str(user.id), openai_key
            )
            if rag_chunks:
                rag_msg = SystemMessage(content=_format_rag_context(rag_chunks))
                lc_messages = [lc_messages[0], rag_msg, *lc_messages[1:]]
                logger.info(
                    "rag_context_injected",
                    user_id=str(user.id),
                    chunk_count=len(rag_chunks),
                )
        except Exception:
            logger.warning("rag_auto_inject_failed", exc_info=True)
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/api/test_chat_rag.py -v
```

Expected: PASS (or skip if fixtures unavailable — the import + logic is testable via integration)

**Step 6: Run full test suite to ensure no regressions**

```bash
uv run pytest tests/ -v
```

Expected: all existing tests still PASS

**Step 7: Commit**

```bash
git add app/api/chat.py tests/api/test_chat_rag.py
git commit -m "feat: auto-inject RAG context into web chat stream"
```

---

## Task 5.5: Auto-Inject RAG Context in Gateway

**Files:**
- Modify: `backend/app/gateway/router.py` — add retrieval in `_invoke_agent()`
- Modify: `backend/tests/gateway/test_gateway_agent.py` — add RAG injection test

**Context:** `router.py:319-355` has `_invoke_agent()` which builds `lc_messages` and calls `create_graph()`. We add the same auto-retrieval step here, reusing `_format_rag_context` from `chat.py` (extract to shared location or duplicate the short function).

---

**Step 1: Extract `_format_rag_context` to shared module**

Move the helper to `app/rag/retriever.py` (add after `retrieve_context`):

```python
def format_rag_context(chunks: list["RetrievedChunk"]) -> str:
    """Format retrieved chunks into a system message content block."""
    lines = ["[Knowledge Base Context]"]
    for chunk in chunks:
        lines.append(
            f'Document: "{chunk.document_name}" (relevance: {chunk.score:.2f})'
        )
        lines.append(chunk.content)
        lines.append("")
    lines.append(
        "Use the above context to answer the user's question. "
        "Cite document names when referencing this content."
    )
    return "\n".join(lines)
```

Update `app/api/chat.py` to import `format_rag_context` from `app.rag.retriever` instead of the local `_format_rag_context` function (delete the local one).

**Step 2: Write failing test**

Add to `backend/tests/gateway/test_gateway_agent.py`:

```python
@pytest.mark.asyncio
async def test_gateway_agent_injects_rag_context(
    mock_db_session: AsyncMock,
) -> None:
    """_invoke_agent should prepend RAG context when retrieve_context returns chunks."""
    from app.rag.retriever import RetrievedChunk

    chunks = [RetrievedChunk("gateway_doc.pdf", "Gateway relevant info", 0.82)]
    captured: list = []

    async def fake_invoke(state):
        captured.extend(state.messages)
        from langchain_core.messages import AIMessage
        return {"messages": [*state.messages, AIMessage(content="ok")]}

    mock_graph = MagicMock()
    mock_graph.ainvoke = fake_invoke

    with (
        patch("app.gateway.router.retrieve_context", new_callable=AsyncMock, return_value=chunks),
        patch("app.gateway.router.create_graph", return_value=mock_graph),
    ):
        router = _make_router_with_db(mock_db_session)
        await router._invoke_agent(
            provider="deepseek",
            model_name="deepseek-chat",
            api_keys=["key"],
            raw_keys={},
            enabled_tools=["datetime"],
            user_id="user-1",
            lc_messages=[SystemMessage(content="system"), HumanMessage(content="hi")],
            channel="fake",
        )

    context_msgs = [
        m for m in captured if "[Knowledge Base Context]" in str(getattr(m, "content", ""))
    ]
    assert len(context_msgs) == 1
    assert "gateway_doc.pdf" in context_msgs[0].content
```

**Step 3: Run test to verify it fails**

```bash
uv run pytest tests/gateway/test_gateway_agent.py -v
```

Expected: FAIL — `retrieve_context` not imported in `router.py`

**Step 4: Modify `app/gateway/router.py`**

Add import at the top:

```python
from app.rag.retriever import format_rag_context, retrieve_context
```

In `_invoke_agent()`, find where `lc_messages` is passed to `create_graph()` (around line 332) and add before it:

```python
        # Auto-inject RAG context when user has relevant documents
        openai_key_for_rag = resolve_api_key("openai", raw_keys)
        if openai_key_for_rag:
            try:
                last_human = next(
                    (m.content for m in reversed(lc_messages) if isinstance(m, HumanMessage)),
                    "",
                )
                rag_chunks = await retrieve_context(
                    last_human, user_id, openai_key_for_rag
                )
                if rag_chunks:
                    rag_msg = SystemMessage(content=format_rag_context(rag_chunks))
                    lc_messages = [lc_messages[0], rag_msg, *lc_messages[1:]]
                    logger.info(
                        "gateway_rag_context_injected",
                        user_id=user_id,
                        chunk_count=len(rag_chunks),
                        channel=channel,
                    )
            except Exception:
                logger.warning("gateway_rag_auto_inject_failed", exc_info=True)
```

**Step 5: Update `_format_rag_context` usage in `chat.py`**

Change the import in `chat.py`:
```python
from app.rag.retriever import format_rag_context, retrieve_context
```

Replace the local `_format_rag_context` call with `format_rag_context(rag_chunks)` and delete the local helper function.

**Step 6: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS

**Step 7: Run lint and type-check**

```bash
uv run ruff check --fix && uv run ruff format && uv run mypy app
```

Expected: no errors

**Step 8: Commit**

```bash
git add app/gateway/router.py app/api/chat.py app/rag/retriever.py tests/gateway/test_gateway_agent.py
git commit -m "feat: auto-inject RAG context in gateway channel messages"
```

---

## Execution Order

| Task | Dependency | Focus |
|------|-----------|-------|
| 5.1 Retriever module | none | New `retriever.py` with `RetrievedChunk` |
| 5.2 Store doc_name in Qdrant | 5.1 (uses retriever in test) | Indexer + documents.py |
| 5.3 Update RAG tool | 5.1 | Replace `search_documents` with `retrieve_context` |
| 5.4 Auto-inject in web chat | 5.1, 5.3 | `chat.py` pre-injection |
| 5.5 Auto-inject in gateway | 5.1, 5.4 (shared formatter) | `router.py` + extract formatter |

## Verification Checklist

```bash
# 1. Lint + format
cd backend && uv run ruff check --fix && uv run ruff format

# 2. Type check
uv run mypy app

# 3. Full test suite
uv run pytest tests/ -v

# 4. Pre-commit hooks
cd .. && pre-commit run --all-files

# 5. Manual smoke test (requires running stack)
# Upload a document, send a message asking about it, verify citation in response
```
