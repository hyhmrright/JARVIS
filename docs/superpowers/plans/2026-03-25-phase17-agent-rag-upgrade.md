# Phase 17: Agent & RAG Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 10 reliability, security, and correctness bugs in the agent execution pipeline, RAG system, and document management.

**Architecture:** All changes are surgical fixes to existing files — no new services. Python 3.13 `asyncio.timeout()` wraps LLM graph streams; a new `core/network.py` module centralises SSRF-safe DNS checks; chunker gains CJK detection; memory injection gets a char-cap guard.

**Tech Stack:** FastAPI, LangGraph, asyncio (Python 3.13), python-magic (libmagic), SQLAlchemy async, Qdrant, MinIO

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `backend/app/core/config.py` | Modify | Add `graph_timeout_seconds=120`, `tool_search_timeout=15`, `tool_image_timeout=60`, `tool_shell_max_timeout=120` |
| `backend/app/core/network.py` | **Create** | `resolve_and_check_ip(hostname)` — async SSRF-safe DNS checker |
| `backend/app/api/chat.py` | Modify | Wrap `graph.astream` calls with `asyncio.timeout`; char-cap `_build_memory_message`; log `compact_messages` errors |
| `backend/app/tools/search_tool.py` | Modify | `asyncio.wait_for` wrapper for tavily search |
| `backend/app/tools/image_gen_tool.py` | Modify | Add `timeout=60` to `client.images.generate` |
| `backend/app/tools/browser_tool.py` | Modify | Replace `_is_blocked` IP-only check with `resolve_and_check_ip` |
| `backend/app/tools/web_fetch_tool.py` | Modify | Replace `is_safe_url` with `resolve_and_check_ip` call |
| `backend/app/tools/subagent_tool.py` | Modify | Wrap `graph.ainvoke` with `asyncio.timeout` |
| `backend/app/tools/code_exec_tool.py` | Modify | Cap `timeout` param at `settings.tool_shell_max_timeout` |
| `backend/app/rag/chunker.py` | Modify | Detect CJK content, split by character when >30% CJK |
| `backend/app/agent/supervisor.py` | Modify | `get_llm` → `get_llm_with_fallback` |
| `backend/app/api/documents.py` | Modify | Rename: sync Qdrant `set_payload`; Upload: MIME magic-byte check + try/finally orphan cleanup |
| `backend/Dockerfile` | Modify | Add `libmagic1` to runtime apt-get install |
| `backend/pyproject.toml` | Modify | Add `python-magic` dependency |
| `backend/tests/api/test_documents.py` | Modify | Tests for MIME rejection, orphan cleanup, rename Qdrant sync |
| `backend/tests/tools/test_network.py` | **Create** | Unit tests for `resolve_and_check_ip` |
| `backend/tests/rag/test_chunker.py` | Modify/Create | Tests for CJK chunking path |

---

### Task 1: Config — add timeout/cap settings

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Read the file**

Run: `cat backend/app/core/config.py`

- [ ] **Step 2: Write the failing test**

No direct unit test needed — config is tested implicitly by downstream tests. Skip to implementation.

- [ ] **Step 3: Add settings fields**

In `class Settings(BaseSettings)`, add after existing fields:

```python
# Agent / tool timeouts
graph_timeout_seconds: int = 120
tool_search_timeout: int = 15
tool_image_timeout: int = 60
tool_shell_max_timeout: int = 120
```

- [ ] **Step 4: Verify import compiles**

Run: `cd backend && uv run python -c "from app.core.config import settings; print(settings.graph_timeout_seconds)"`
Expected: `120`

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py
git commit -m "feat: add agent/tool timeout settings to config"
```

---

### Task 2: core/network.py — SSRF-safe DNS resolver

**Files:**
- Create: `backend/app/core/network.py`
- Create: `backend/tests/tools/test_network.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/tools/test_network.py
import pytest
from unittest.mock import patch
from app.core.network import resolve_and_check_ip


@pytest.mark.anyio
async def test_private_ipv4_blocked():
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("192.168.1.1", 0))]):
        assert await resolve_and_check_ip("internal.local") is False


@pytest.mark.anyio
async def test_loopback_blocked():
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 0))]):
        assert await resolve_and_check_ip("localhost") is False


@pytest.mark.anyio
async def test_public_ip_allowed():
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
        assert await resolve_and_check_ip("example.com") is True


@pytest.mark.anyio
async def test_unresolvable_host_blocked():
    import socket
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("no such host")):
        assert await resolve_and_check_ip("does-not-exist.invalid") is False


@pytest.mark.anyio
async def test_ipv6_loopback_blocked():
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("::1", 0, 0, 0))]):
        assert await resolve_and_check_ip("ip6-localhost") is False


@pytest.mark.anyio
async def test_link_local_blocked():
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("169.254.169.254", 0))]):
        assert await resolve_and_check_ip("metadata.internal") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/tools/test_network.py -v`
Expected: ImportError (module doesn't exist yet)

- [ ] **Step 3: Implement network.py**

```python
"""SSRF-safe DNS resolution utilities."""

import ipaddress
import socket
from functools import partial

import anyio


_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / AWS metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
        return any(ip in net for net in _BLOCKED_NETWORKS)
    except ValueError:
        return True  # unparseable → block


async def resolve_and_check_ip(hostname: str) -> bool:
    """Return True only if hostname resolves to a public routable IP.

    Performs DNS resolution in a thread pool to avoid blocking the event loop.
    Returns False for private/loopback/link-local IPs and on resolution errors.
    """
    try:
        results = await anyio.to_thread.run_sync(
            partial(socket.getaddrinfo, hostname, None)
        )
        for result in results:
            addr = result[4][0]
            if _is_private_ip(addr):
                return False
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/tools/test_network.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/network.py backend/tests/tools/test_network.py
git commit -m "feat: add SSRF-safe DNS resolver in core/network.py"
```

---

### Task 3: SSRF hardening — browser_tool + web_fetch_tool

**Files:**
- Modify: `backend/app/tools/browser_tool.py`
- Modify: `backend/app/tools/web_fetch_tool.py`
- Modify: `backend/app/api/documents.py` (uses `is_safe_url`)

- [ ] **Step 1: Read the files**

Read `backend/app/tools/browser_tool.py` lines 1-60 and `backend/app/tools/web_fetch_tool.py`.

- [ ] **Step 2: Replace browser_tool `_is_blocked`**

In `browser_tool.py`, replace the `_is_blocked` function and its caller `_fetch_page` so that DNS hostnames are also checked:

```python
# Replace the entire _is_blocked function with:
from app.core.network import resolve_and_check_ip

async def _is_safe_url(url: str) -> bool:
    """Return False if URL resolves to a private/internal IP."""
    from urllib.parse import urlparse
    try:
        hostname = urlparse(url).hostname
        if not hostname:
            return False
        # Check raw IP literals first
        try:
            import ipaddress
            from app.core.network import _is_private_ip
            ipaddress.ip_address(hostname)
            return not _is_private_ip(hostname)
        except ValueError:
            pass
        return await resolve_and_check_ip(hostname)
    except Exception:
        return False
```

In `_fetch_page` (or equivalent), change the guard from `if _is_blocked(url):` to:
```python
if not await _is_safe_url(url):
    return "Error: URL is not allowed (private/internal address)"
```

- [ ] **Step 3: Replace web_fetch_tool `is_safe_url`**

In `web_fetch_tool.py`, replace `is_safe_url` to use DNS resolution:

```python
from app.core.network import resolve_and_check_ip, _is_private_ip

async def is_safe_url(url: str) -> bool:
    """Return False if URL points to a private or internal address."""
    from urllib.parse import urlparse
    try:
        hostname = urlparse(url).hostname
        if not hostname:
            return False
        try:
            import ipaddress
            ipaddress.ip_address(hostname)
            return not _is_private_ip(hostname)
        except ValueError:
            pass
        return await resolve_and_check_ip(hostname)
    except Exception:
        return False
```

Update callers: change `if not is_safe_url(url):` to `if not await is_safe_url(url):`.

Also update `documents.py` which imports `is_safe_url`:
- Change its usage to `await is_safe_url(url)` if it's currently called synchronously.

- [ ] **Step 4: Lint check**

Run: `cd backend && uv run ruff check app/tools/browser_tool.py app/tools/web_fetch_tool.py app/api/documents.py --fix`

- [ ] **Step 5: Import check**

Run: `cd backend && uv run pytest --collect-only -q 2>&1 | head -20`
Expected: no ImportError

- [ ] **Step 6: Commit**

```bash
git add backend/app/tools/browser_tool.py backend/app/tools/web_fetch_tool.py backend/app/api/documents.py
git commit -m "fix: harden SSRF protection with DNS resolution in browser and fetch tools"
```

---

### Task 4: Agent execution timeout

**Files:**
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/tools/subagent_tool.py`

- [ ] **Step 1: Read the relevant sections**

Read `backend/app/api/chat.py` lines 700-730 and lines 1035-1060.
Read `backend/app/tools/subagent_tool.py` lines 70-90.

- [ ] **Step 2: Wrap graph.astream in chat.py (main stream, ~line 717)**

Locate the `async for chunk in graph.astream(state, ...)` call in the main streaming handler. Wrap it:

```python
import asyncio
from app.core.config import settings

try:
    async with asyncio.timeout(settings.graph_timeout_seconds):
        async for chunk in graph.astream(state, config={"recursion_limit": 50}):
            # ... existing chunk processing ...
except asyncio.TimeoutError:
    timeout_msg = f"data: {json.dumps({'type': 'error', 'content': 'Request timed out'})}\n\n"
    yield timeout_msg
    return
```

- [ ] **Step 3: Wrap graph.astream in chat.py (regenerate endpoint, ~line 1045)**

Apply the same `asyncio.timeout` wrapper to the regenerate endpoint's `graph.astream` call.

- [ ] **Step 4: Fix compact_messages silent swallow (~line 983)**

Locate:
```python
except Exception:
    pass
```

Change to:
```python
except Exception as exc:
    logger.warning("compact_messages_failed", error=str(exc))
```

- [ ] **Step 5: Wrap subagent_tool graph.ainvoke (~line 78)**

```python
try:
    async with asyncio.timeout(settings.graph_timeout_seconds):
        result = await graph.ainvoke(state, config={"recursion_limit": 30})
except asyncio.TimeoutError:
    return "Error: Sub-agent timed out"
```

- [ ] **Step 6: Lint and import check**

```bash
cd backend
uv run ruff check app/api/chat.py app/tools/subagent_tool.py --fix
uv run pytest --collect-only -q 2>&1 | head -20
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/chat.py backend/app/tools/subagent_tool.py
git commit -m "feat: add asyncio.timeout to graph.astream and subagent.ainvoke"
```

---

### Task 5: Tool timeouts — search, image_gen, shell cap

**Files:**
- Modify: `backend/app/tools/search_tool.py`
- Modify: `backend/app/tools/image_gen_tool.py`
- Modify: `backend/app/tools/code_exec_tool.py`

- [ ] **Step 1: Read all three files**

Read each file in full.

- [ ] **Step 2: search_tool — asyncio.wait_for**

In `_web_search_impl`, wrap the tavily call:

```python
import asyncio
from app.core.config import settings

try:
    results = await asyncio.wait_for(
        client.search(query=query, max_results=max_results),
        timeout=settings.tool_search_timeout,
    )
except asyncio.TimeoutError:
    return "Search timed out. Please try again."
```

- [ ] **Step 3: image_gen_tool — httpx timeout**

In `_arun`, change:
```python
response = await client.images.generate(
    model="dall-e-3",
    prompt=prompt,
    size=size,
    n=1,
)
```
to:
```python
response = await client.images.generate(
    model="dall-e-3",
    prompt=prompt,
    size=size,
    n=1,
    timeout=settings.tool_image_timeout,
)
```

Add `from app.core.config import settings` at top of file.

- [ ] **Step 4: code_exec_tool — cap timeout param**

In `_run` (or `_arun`), find where `timeout` is passed to `subprocess.run`. Add a cap:

```python
from app.core.config import settings

# cap user-supplied timeout
effective_timeout = min(timeout, settings.tool_shell_max_timeout)
proc = subprocess.run(..., timeout=effective_timeout, ...)
```

- [ ] **Step 5: Lint check**

```bash
cd backend && uv run ruff check app/tools/search_tool.py app/tools/image_gen_tool.py app/tools/code_exec_tool.py --fix
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/tools/search_tool.py backend/app/tools/image_gen_tool.py backend/app/tools/code_exec_tool.py
git commit -m "feat: add timeouts to search, image_gen, and shell tools"
```

---

### Task 6: RAG CJK chunking

**Files:**
- Modify: `backend/app/rag/chunker.py`
- Modify/Create: `backend/tests/rag/test_chunker.py`

- [ ] **Step 1: Read chunker.py**

Run: `cat backend/app/rag/chunker.py`

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/rag/test_chunker.py
from app.rag.chunker import chunk_text


def test_english_text_word_split():
    text = "hello world " * 600  # 1200 words
    chunks = chunk_text(text)
    assert len(chunks) > 1
    # Each chunk should be under 600 words
    for chunk in chunks:
        assert len(chunk.split()) <= 600


def test_cjk_text_char_split():
    # Pure Chinese text — should split by character, not by space
    text = "这是一段中文文字。" * 300  # long CJK text
    chunks = chunk_text(text)
    assert len(chunks) > 0
    # Should not produce a single word per "token" (words would be whole text)
    # Each chunk should be a string with Chinese characters
    assert all(len(c) > 0 for c in chunks)
    # Char-split: each chunk length should be bounded
    for chunk in chunks:
        assert len(chunk) <= 1600  # 500 chars * 2 bytes est + overlap, generous bound


def test_mixed_text_uses_cjk_path():
    # >30% CJK → takes CJK path
    cjk_part = "中文内容" * 50
    latin_part = "english " * 30
    text = cjk_part + latin_part  # CJK >> 30%
    chunks = chunk_text(text)
    assert len(chunks) > 0


def test_mostly_latin_with_some_cjk_uses_word_path():
    # <30% CJK → word-split path
    latin = "word " * 200
    cjk = "中文" * 10
    text = latin + cjk
    chunks = chunk_text(text)
    assert len(chunks) > 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/rag/test_chunker.py -v`
Note which fail (CJK tests will not chunk correctly with current word-split logic).

- [ ] **Step 4: Implement CJK-aware chunker**

Replace `chunker.py` with:

```python
"""Text chunker with CJK-aware splitting."""

_WORD_CHUNK_SIZE = 500
_WORD_OVERLAP = 50
_CJK_CHUNK_SIZE = 500  # characters
_CJK_OVERLAP = 50
_CJK_THRESHOLD = 0.3


def _cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff" or "\u3040" <= c <= "\u30ff")
    return cjk_count / len(text)


def _chunk_by_chars(text: str, size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return [c for c in chunks if c.strip()]


def _chunk_by_words(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + size
        chunks.append(" ".join(words[start:end]))
        start += size - overlap
    return [c for c in chunks if c.strip()]


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks.

    Uses character-based splitting for CJK-heavy text (>30% CJK characters)
    and word-based splitting for Latin/mixed text.
    """
    if _cjk_ratio(text) > _CJK_THRESHOLD:
        return _chunk_by_chars(text, _CJK_CHUNK_SIZE, _CJK_OVERLAP)
    return _chunk_by_words(text, _WORD_CHUNK_SIZE, _WORD_OVERLAP)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest tests/rag/test_chunker.py -v`
Expected: 4 PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/app/rag/chunker.py backend/tests/rag/test_chunker.py
git commit -m "feat: CJK-aware RAG chunking (char-split for >30% CJK content)"
```

---

### Task 7: Memory injection overflow protection

**Files:**
- Modify: `backend/app/api/chat.py`

- [ ] **Step 1: Read the _build_memory_message function**

Read `backend/app/api/chat.py` lines 60-85.

- [ ] **Step 2: Write failing test**

```python
# In tests/api/test_chat.py or a new test — verify char cap
# This is a unit-level test of the helper; add to existing chat tests or inline check.
# Since _build_memory_message is internal, we test via the behaviour in integration.
# For now, verify the constant exists and the logic is correct by reading it.
```

(No new test file needed — the cap is a simple defensive guard; existing chat tests cover end-to-end.)

- [ ] **Step 3: Add char-cap constant and update function**

At the top of `chat.py` (near `_MEMORY_PROMPT_LIMIT = 100`), add:

```python
_MEMORY_CHAR_LIMIT = 8000
```

In `_build_memory_message`, change the loop that builds the memory string to stop when `_MEMORY_CHAR_LIMIT` is exceeded:

```python
async def _build_memory_message(db: AsyncSession, user_id: str) -> str | None:
    result = await db.execute(
        select(UserMemory)
        .where(UserMemory.user_id == user_id)
        .order_by(UserMemory.created_at.desc())
        .limit(_MEMORY_PROMPT_LIMIT)
    )
    memories = result.scalars().all()
    if not memories:
        return None
    lines: list[str] = []
    total_chars = 0
    for m in reversed(memories):
        line = f"- {m.content}"
        if total_chars + len(line) > _MEMORY_CHAR_LIMIT:
            break
        lines.append(line)
        total_chars += len(line)
    if not lines:
        return None
    return "User memories:\n" + "\n".join(lines)
```

- [ ] **Step 4: Lint check**

Run: `cd backend && uv run ruff check app/api/chat.py --fix`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/chat.py
git commit -m "fix: cap memory injection at 8000 chars to prevent prompt overflow"
```

---

### Task 8: LLM fallback in supervisor

**Files:**
- Modify: `backend/app/agent/supervisor.py`

- [ ] **Step 1: Read the file**

Read `backend/app/agent/supervisor.py` lines 50-70.

- [ ] **Step 2: Change get_llm to get_llm_with_fallback**

Find the line (approximately line 58):
```python
llm = get_llm(...)
```

Change to:
```python
llm = get_llm_with_fallback(...)
```

Ensure `get_llm_with_fallback` is imported at the top of the file. Check `agent/llm.py` for the correct import name.

- [ ] **Step 3: Lint check**

Run: `cd backend && uv run ruff check app/agent/supervisor.py --fix`

- [ ] **Step 4: Import check**

Run: `cd backend && uv run pytest --collect-only -q 2>&1 | head -20`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/supervisor.py
git commit -m "fix: supervisor uses get_llm_with_fallback for resilience"
```

---

### Task 9: Document rename — Qdrant set_payload sync

**Files:**
- Modify: `backend/app/api/documents.py`

- [ ] **Step 1: Read the rename endpoint**

Read `backend/app/api/documents.py` lines 120-160.

- [ ] **Step 2: Write failing test**

In `backend/tests/api/test_documents.py`, add (or verify existence of) a test that:
1. Uploads a document
2. Renames it via `PATCH /api/documents/{id}`
3. Asserts the returned document has the new filename
4. (Integration) Verifies Qdrant payload would be updated

For now, add a test that checks the response:

```python
async def test_rename_document_updates_filename(auth_client, tmp_path):
    """PATCH /api/documents/{id} updates filename in DB."""
    # Upload a small text file
    content = b"hello world content"
    resp = await auth_client.post(
        "/api/documents",
        files={"file": ("original.txt", content, "text/plain")},
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    # Rename
    rename_resp = await auth_client.patch(
        f"/api/documents/{doc_id}",
        json={"filename": "renamed.txt"},
    )
    assert rename_resp.status_code == 200
    assert rename_resp.json()["filename"] == "renamed.txt"
```

- [ ] **Step 3: Add Qdrant set_payload after filename update**

In the rename endpoint, after `doc.filename = body.filename`, add:

```python
# Sync new filename to Qdrant vector metadata
from app.infra.qdrant import get_qdrant_client
try:
    qdrant = await get_qdrant_client()
    collection = f"user_{current_user.id}"
    await qdrant.set_payload(
        collection_name=collection,
        payload={"filename": body.filename},
        points=models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=str(doc.id)),
                )
            ]
        ),
    )
except Exception as exc:
    logger.warning("qdrant_rename_sync_failed", doc_id=str(doc.id), error=str(exc))
```

Note: wrap in try/except so a Qdrant failure doesn't prevent the DB rename.

- [ ] **Step 4: Lint check**

Run: `cd backend && uv run ruff check app/api/documents.py --fix`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/documents.py backend/tests/api/test_documents.py
git commit -m "fix: sync Qdrant payload on document rename"
```

---

### Task 10: File upload — MIME validation + orphan cleanup

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/api/documents.py`

- [ ] **Step 1: Read the upload endpoint and Dockerfile**

Read `backend/app/api/documents.py` lines 180-260.
Read `backend/Dockerfile`.

- [ ] **Step 2: Add libmagic1 to Dockerfile**

In the runtime stage of `backend/Dockerfile`, find the `apt-get install` line that has `libpq5 curl`. Add `libmagic1`:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 3: Add python-magic dependency**

```bash
cd backend && uv add python-magic
```

- [ ] **Step 4: Write failing test for MIME rejection**

In `backend/tests/api/test_documents.py`, add:

```python
async def test_upload_rejects_disguised_executable(auth_client):
    """Upload with .txt extension but ELF magic bytes must be rejected."""
    elf_magic = b"\x7fELF" + b"\x00" * 100  # ELF header magic
    resp = await auth_client.post(
        "/api/documents",
        files={"file": ("evil.txt", elf_magic, "text/plain")},
    )
    assert resp.status_code == 400


async def test_upload_accepts_valid_pdf(auth_client):
    """Upload with valid PDF magic bytes and .pdf extension is accepted."""
    pdf_magic = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    resp = await auth_client.post(
        "/api/documents",
        files={"file": ("valid.pdf", pdf_magic, "application/pdf")},
    )
    # May fail at extraction but should pass MIME check (not 400)
    assert resp.status_code != 400
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_documents.py::test_upload_rejects_disguised_executable -v`
Expected: FAIL (currently accepts ELF magic)

- [ ] **Step 6: Implement MIME check + try/finally orphan cleanup in upload**

In the upload handler in `documents.py`, after reading the file bytes and checking extension, add MIME validation:

```python
import magic  # python-magic

# MIME magic-byte validation
ALLOWED_MIME_PREFIXES = {
    "text/", "application/pdf", "application/msword",
    "application/vnd.openxmlformats", "application/vnd.ms-",
    "image/png", "image/jpeg", "image/gif", "image/webp",
}

file_bytes = await file.read()
await file.seek(0)

detected_mime = magic.from_buffer(file_bytes[:2048], mime=True)
if not any(detected_mime.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
    raise HTTPException(
        status_code=400,
        detail=f"File type '{detected_mime}' is not allowed",
    )
```

Wrap the MinIO upload and DB insert in try/finally for orphan cleanup:

```python
object_name = None
try:
    object_name = f"{current_user.id}/{doc.id}/{filename}"
    # ... existing MinIO upload code ...
    # ... existing DB commit code ...
except Exception:
    if object_name:
        try:
            minio = get_minio_client()
            await anyio.to_thread.run_sync(
                lambda: minio.remove_object(settings.minio_bucket, object_name)
            )
        except Exception:
            pass  # best-effort cleanup
    raise
```

- [ ] **Step 7: Run tests**

Run: `cd backend && uv run pytest tests/api/test_documents.py -v`
Expected: MIME tests pass

- [ ] **Step 8: Lint check**

Run: `cd backend && uv run ruff check app/api/documents.py --fix`

- [ ] **Step 9: Commit**

```bash
git add backend/Dockerfile backend/pyproject.toml backend/uv.lock \
        backend/app/api/documents.py backend/tests/api/test_documents.py
git commit -m "feat: MIME magic-byte validation and MinIO orphan cleanup on upload"
```

---

### Task 11: Final static checks + push

- [ ] **Step 1: Run full static checks**

```bash
cd backend
uv run ruff check --fix && uv run ruff format
uv run mypy app
uv run pytest --collect-only -q
```

Expected: no errors

- [ ] **Step 2: Run full test suite**

```bash
cd backend && uv run pytest tests/ -x -q --tb=short
```

Expected: all tests pass (or only pre-existing failures unrelated to Phase 17)

- [ ] **Step 3: Run frontend checks**

```bash
cd frontend
bun run lint:fix
bun run type-check
```

- [ ] **Step 4: Run quality loop**

Execute `/simplify` skill, then `superpowers:code-reviewer` task agent.

- [ ] **Step 5: Commit any simplify fixes and push**

```bash
git add -A && git commit -m "chore: Phase 17 simplify pass"
git push origin dev
```
