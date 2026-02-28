# JARVIS Full-Capability Assistant — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform JARVIS from a Web-only chat platform into a full-capability local AI assistant with RAG integration, agent tool execution, multi-channel access, multi-agent orchestration, plugin system, and voice/canvas experience.

**Architecture:** Incremental evolution of the existing FastAPI + LangGraph + Vue 3 stack. Each Phase adds a self-contained capability layer. New tools follow the `@tool` + `_TOOL_MAP` registration pattern. New API endpoints follow the `APIRouter` + `main.py include_router` pattern. New frontend features extend the existing Pinia stores and Vue pages.

**Tech Stack:** Python 3.13, FastAPI, LangGraph, SQLAlchemy (async), Qdrant, Redis, MinIO, Docker, Vue 3, TypeScript, Pinia, Vite

---

## Phase 1: Core Completion — RAG Integration + Agent Tool Enhancement

### Task 1.1: Connect RAG Search to Agent

**Files:**
- Create: `backend/app/tools/rag_tool.py`
- Modify: `backend/app/agent/graph.py` (add to `_TOOL_MAP`)
- Modify: `backend/app/db/models.py` (add `"rag_search"` to default `enabled_tools`)
- Test: `backend/tests/tools/test_rag_tool.py`

**Step 1: Write the failing test**

```python
# backend/tests/tools/test_rag_tool.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_rag_search_returns_results():
    mock_results = ["chunk 1 text", "chunk 2 text"]
    with patch("app.tools.rag_tool.search_documents", new_callable=AsyncMock, return_value=mock_results):
        from app.tools.rag_tool import _rag_search_impl
        result = await _rag_search_impl(query="test query", user_id="user-123", api_key="sk-test")
    assert "chunk 1 text" in result
    assert "chunk 2 text" in result

@pytest.mark.asyncio
async def test_rag_search_no_results():
    with patch("app.tools.rag_tool.search_documents", new_callable=AsyncMock, return_value=[]):
        from app.tools.rag_tool import _rag_search_impl
        result = await _rag_search_impl(query="unknown", user_id="user-123", api_key="sk-test")
    assert "没有找到" in result or "No relevant" in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/tools/test_rag_tool.py -v`
Expected: FAIL (module not found)

**Step 3: Implement the RAG search tool**

```python
# backend/app/tools/rag_tool.py
"""RAG knowledge base search tool for the LangGraph agent."""

from langchain_core.tools import tool

from app.rag.indexer import search_documents


async def _rag_search_impl(
    query: str, user_id: str, api_key: str, top_k: int = 5
) -> str:
    results = await search_documents(user_id, query, api_key, top_k=top_k)
    if not results:
        return "没有找到相关的知识库内容。"
    formatted = []
    for i, text in enumerate(results, 1):
        formatted.append(f"[{i}] {text}")
    return "\n\n".join(formatted)


def create_rag_search_tool(user_id: str, api_key: str):
    """Factory that creates a rag_search tool closed over user context."""

    @tool
    async def rag_search(query: str) -> str:
        """Search the user's knowledge base for relevant documents.
        Use this when the user asks questions that might be answered
        by their uploaded documents."""
        return await _rag_search_impl(query, user_id, api_key)

    return rag_search
```

**Step 4: Update graph.py to support context-aware tools**

Modify `backend/app/agent/graph.py`:
- Import `create_rag_search_tool` from `app.tools.rag_tool`
- Add `user_id: str | None = None` and `api_key: str | None = None` parameters to `create_graph()`
- In `create_graph()`, if `"rag_search"` is in enabled_tools and `user_id`/`api_key` are provided, call `create_rag_search_tool(user_id, api_key)` and add to tools list
- Update `_TOOL_MAP` comment to document the special handling

**Step 5: Update chat.py to pass user context to graph**

Modify `backend/app/api/chat.py`:
- In `generate()`, pass `user_id=str(user.id)` and `api_key=resolve_api_key("openai", llm.raw_keys)` to `create_graph()`
- Handle the case where no OpenAI key is available (RAG tool silently excluded)

**Step 6: Update default enabled_tools**

Modify `backend/app/db/models.py`:
- Change `enabled_tools` default from `["search","code_exec","datetime"]` to `["search","code_exec","datetime","rag_search"]`

**Step 7: Run tests to verify**

Run: `cd backend && uv run pytest tests/tools/test_rag_tool.py -v`
Expected: PASS

**Step 8: Commit**

```bash
git add backend/app/tools/rag_tool.py backend/app/agent/graph.py backend/app/api/chat.py backend/app/db/models.py backend/tests/tools/test_rag_tool.py
git commit -m "feat: connect RAG knowledge base search to agent conversation flow"
```

---

### Task 1.2: Add Web Search Tool (Tavily)

**Files:**
- Modify: `backend/app/tools/search_tool.py` (replace DuckDuckGo with Tavily)
- Modify: `backend/pyproject.toml` (add `tavily-python` dependency)
- Test: `backend/tests/tools/test_search_tool.py`

**Step 1: Add Tavily dependency**

Run: `cd backend && uv add tavily-python`

**Step 2: Write failing test**

```python
# backend/tests/tools/test_search_tool.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_web_search_returns_results():
    mock_response = {
        "results": [
            {"title": "Result 1", "url": "https://example.com/1", "content": "Content 1"},
            {"title": "Result 2", "url": "https://example.com/2", "content": "Content 2"},
        ]
    }
    with patch("app.tools.search_tool.TavilySearchResults") as MockTavily:
        mock_instance = AsyncMock()
        mock_instance.ainvoke.return_value = mock_response["results"]
        MockTavily.return_value = mock_instance
        from app.tools.search_tool import _web_search_impl
        result = await _web_search_impl(query="test", api_key="tvly-test")
    assert "Result 1" in result
```

**Step 3: Implement Tavily-based search**

```python
# backend/app/tools/search_tool.py
"""Web search tool using Tavily API."""

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import tool


async def _web_search_impl(query: str, api_key: str, max_results: int = 5) -> str:
    search = TavilySearchResults(max_results=max_results, api_key=api_key)
    results = await search.ainvoke({"query": query})
    if not results:
        return "No search results found."
    formatted = []
    for r in results:
        title = r.get("title", "")
        url = r.get("url", "")
        content = r.get("content", "")
        formatted.append(f"**{title}**\n{url}\n{content}")
    return "\n\n---\n\n".join(formatted)


def create_web_search_tool(api_key: str):
    """Factory that creates a web_search tool closed over API key."""

    @tool
    async def web_search(query: str) -> str:
        """Search the web for current information. Use when you need
        up-to-date facts, news, or information not in your training data."""
        return await _web_search_impl(query, api_key)

    return web_search
```

**Step 4: Update graph.py** — Convert `web_search` from static tool to factory pattern (like rag_search). Need Tavily API key from user settings or env var.

**Step 5: Update Settings** — Add `TAVILY_API_KEY` to `core/config.py` and `.env` template. Add UI field in `SettingsPage.vue` for Tavily key.

**Step 6: Run tests, commit**

```bash
git commit -m "feat: upgrade web search from DuckDuckGo to Tavily API"
```

---

### Task 1.3: Add Web Fetch Tool

**Files:**
- Create: `backend/app/tools/web_fetch_tool.py`
- Modify: `backend/app/agent/graph.py` (add to `_TOOL_MAP`)
- Modify: `backend/pyproject.toml` (add `trafilatura` dependency)
- Test: `backend/tests/tools/test_web_fetch_tool.py`

**Step 1: Add dependency**

Run: `cd backend && uv add trafilatura`

**Step 2: Write failing test**

```python
@pytest.mark.asyncio
async def test_web_fetch_extracts_content():
    html = "<html><body><article><p>Hello world</p></article></body></html>"
    with patch("app.tools.web_fetch_tool.httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        MockClient.return_value = mock_client
        from app.tools.web_fetch_tool import web_fetch
        result = await web_fetch.ainvoke({"url": "https://example.com"})
    assert "Hello world" in result
```

**Step 3: Implement web_fetch tool**

```python
# backend/app/tools/web_fetch_tool.py
"""Web page content extraction tool."""

import httpx
import trafilatura
from langchain_core.tools import tool

_MAX_CONTENT_LENGTH = 8000  # chars, approx 2000 tokens


@tool
async def web_fetch(url: str) -> str:
    """Fetch a web page and extract its readable text content.
    Use this to read articles, documentation, or any web page."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "JARVIS/1.0"})
            resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"Failed to fetch URL: {e}"

    extracted = trafilatura.extract(resp.text, include_links=True, include_tables=True)
    if not extracted:
        return "Could not extract readable content from the page."

    if len(extracted) > _MAX_CONTENT_LENGTH:
        extracted = extracted[:_MAX_CONTENT_LENGTH] + "\n\n[Content truncated]"
    return extracted
```

**Step 4: Register in graph.py** — Add `"web_fetch": web_fetch` to `_TOOL_MAP`.

**Step 5: Run tests, commit**

```bash
git commit -m "feat: add web_fetch tool for extracting web page content"
```

---

### Task 1.4: Stream Tool Call Status in SSE

**Files:**
- Modify: `backend/app/api/chat.py` (emit `tool_start`/`tool_end` SSE events)
- Modify: `frontend/src/stores/chat.ts` (parse tool events)
- Modify: `frontend/src/pages/ChatPage.vue` (display tool status cards)
- Modify: `frontend/src/locales/zh.json` + `en.json` (add tool status i18n keys)

**Step 1: Update SSE generator in chat.py**

In `generate()`, modify the `async for chunk` loop to also handle `"tools"` chunks:

```python
async for chunk in graph.astream(AgentState(messages=lc_messages)):
    if "llm" in chunk:
        ai_msg = chunk["llm"]["messages"][-1]
        # Check for tool_calls in the AI message
        if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
            for tc in ai_msg.tool_calls:
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': tc['name'], 'args': tc['args']})}\n\n"
        # Existing delta logic...
        delta = ai_msg.content[len(full_content):]
        full_content = ai_msg.content
        if delta:
            yield f"data: {json.dumps({'type': 'delta', 'delta': delta, 'content': full_content})}\n\n"
    elif "tools" in chunk:
        tool_msgs = chunk["tools"]["messages"]
        for tm in tool_msgs:
            yield f"data: {json.dumps({'type': 'tool_end', 'tool': tm.name, 'result_preview': tm.content[:200]})}\n\n"
```

**Step 2: Update chat.ts store**

Extend the `Message` interface and SSE parsing:

```typescript
interface ToolCall {
  name: string
  args: Record<string, unknown>
  status: 'running' | 'done'
  result?: string
}
interface Message {
  role: 'human' | 'ai'
  content: string
  toolCalls?: ToolCall[]
}
```

In the SSE read loop, parse `type` field:
- `tool_start`: push to `lastAiMessage.toolCalls[]` with `status: "running"`
- `tool_end`: find matching tool call, set `status: "done"`, set `result`
- `delta`: existing behavior

**Step 3: Update ChatPage.vue**

Add a tool status card component inside the AI message bubble:

```vue
<div v-if="msg.toolCalls?.length" class="tool-calls">
  <div v-for="tc in msg.toolCalls" :key="tc.name" class="tool-call-card">
    <span class="tool-icon">{{ toolIcon(tc.name) }}</span>
    <span class="tool-name">{{ tc.name }}</span>
    <span v-if="tc.status === 'running'" class="tool-spinner">...</span>
    <span v-else class="tool-done">done</span>
    <details v-if="tc.result">
      <summary>{{ t('chat.toolResult') }}</summary>
      <pre>{{ tc.result }}</pre>
    </details>
  </div>
</div>
```

**Step 4: Add i18n keys**

```json
// zh.json additions
"chat": { "toolResult": "工具结果", "toolRunning": "执行中..." }
// en.json additions
"chat": { "toolResult": "Tool Result", "toolRunning": "Running..." }
```

**Step 5: Commit**

```bash
git commit -m "feat: display tool call status in streaming chat UI"
```

---

### Task 1.5: Auth Profile Rotation (Multi API Key)

**Files:**
- Modify: `backend/app/db/models.py` (api_keys schema now supports arrays)
- Modify: `backend/app/core/security.py` (encrypt/decrypt multiple keys per provider)
- Modify: `backend/app/api/deps.py` (`resolve_api_key` with rotation logic)
- Modify: `backend/app/agent/llm.py` (retry with next key on failure)
- Modify: `frontend/src/pages/SettingsPage.vue` (multi-key UI)
- Create: `backend/alembic/versions/xxxx_multi_api_keys.py` (migration if schema changes)

**Design:**

API keys stored as: `{"deepseek": ["sk-key1", "sk-key2"], "openai": ["sk-abc"]}`

LLM factory gets a list of keys. On `AuthenticationError` or `RateLimitError`, try next key with 60s cooldown on failed key.

**Step 1: Update security.py** — `encrypt_api_keys` / `decrypt_api_keys` handle `dict[str, list[str]]` format. Backward compatible with old `dict[str, str]` format (auto-migrate to `[str]`).

**Step 2: Update deps.py** — `resolve_api_key()` updated to return `list[str]`. First tries user keys, then falls back to env var as single-element list.

**Step 3: Update llm.py** — New `get_llm_with_retry(provider, model, api_keys: list[str])` wraps `get_llm()` with key rotation. Returns `(BaseChatModel, api_key_used)`.

**Step 4: Update SettingsPage.vue** — Multi-key input: list of key fields per provider with add/remove buttons.

**Step 5: Run tests, commit**

```bash
git commit -m "feat: support multiple API keys per provider with automatic rotation"
```

---

## Phase 2: Agent Execution — Shell + Browser + Sandbox

### Task 2.1: Shell Execution Tool

**Files:**
- Create: `backend/app/tools/shell_tool.py`
- Modify: `backend/app/agent/graph.py`
- Test: `backend/tests/tools/test_shell_tool.py`

**Implementation:**

```python
# backend/app/tools/shell_tool.py
"""Shell command execution tool with safety controls."""

import asyncio
from langchain_core.tools import tool

_BLOCKED_PATTERNS = {"rm -rf /", "mkfs", "dd if=", ":(){:|:&};:"}
_MAX_OUTPUT = 10000  # chars


@tool
async def shell_exec(command: str, timeout: int = 30) -> str:
    """Run a shell command and return its output.
    Use for system tasks, file operations, running scripts."""
    for blocked in _BLOCKED_PATTERNS:
        if blocked in command:
            return "Blocked: dangerous command pattern detected."

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return f"Command timed out after {timeout}s."

    output = stdout.decode(errors="replace")
    if stderr:
        output += f"\n[stderr]\n{stderr.decode(errors='replace')}"
    if len(output) > _MAX_OUTPUT:
        output = output[:_MAX_OUTPUT] + "\n[Output truncated]"
    return output or "(no output)"
```

Register as `"shell": shell_exec` in `_TOOL_MAP`. Default to `ask` permission level (Phase 2.5).

**Tests:** Verify blocked patterns rejected, timeout works, output truncation.

**Commit:** `git commit -m "feat: add shell execution tool for agent"`

---

### Task 2.2: Docker Sandbox

**Files:**
- Create: `backend/app/sandbox/__init__.py`
- Create: `backend/app/sandbox/manager.py`
- Create: `Dockerfile.sandbox`
- Modify: `docker-compose.yml` (add sandbox service definition)
- Modify: `backend/app/core/config.py` (add sandbox settings)
- Modify: `backend/app/tools/shell_tool.py` (route through sandbox when enabled)

**Implementation:**

`SandboxManager` class:
- `create_sandbox(user_id, session_id)` — Docker container with resource limits
- `exec_in_sandbox(sandbox_id, command, timeout)` — run command inside container
- `destroy_sandbox(sandbox_id)` — cleanup
- Container pool with idle timeout (default 15min)
- Resource limits: 1 CPU, 512MB RAM, 1GB disk

`Dockerfile.sandbox`:
```dockerfile
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git nodejs npm && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir numpy pandas matplotlib requests
WORKDIR /workspace
USER nobody
```

Settings in `config.py`:
```python
sandbox_enabled: bool = False
sandbox_image: str = "jarvis-sandbox:latest"
sandbox_cpu_limit: float = 1.0
sandbox_memory_limit: str = "512m"
sandbox_timeout: int = 300
```

**Commit:** `git commit -m "feat: add Docker sandbox for isolated code execution"`

---

### Task 2.3: Browser Automation Tool

**Files:**
- Create: `backend/app/tools/browser_tool.py`
- Modify: `backend/pyproject.toml` (add `playwright` dependency)
- Modify: `backend/app/agent/graph.py`
- Test: `backend/tests/tools/test_browser_tool.py`

**Implementation:**

```python
# backend/app/tools/browser_tool.py
"""Browser automation tool using Playwright."""

from langchain_core.tools import tool
from playwright.async_api import async_playwright


@tool
async def browser_navigate(url: str, action: str = "extract") -> str:
    """Navigate to a URL and perform an action.
    Actions: 'extract' (get page text), 'screenshot' (take screenshot)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=15000)
            if action == "extract":
                text = await page.inner_text("body")
                return text[:8000] if len(text) > 8000 else text
            elif action == "screenshot":
                screenshot_bytes = await page.screenshot(full_page=True)
                # Store in MinIO and return URL
                return "Screenshot captured successfully."
            return f"Unknown action: {action}"
        finally:
            await browser.close()
```

**Commit:** `git commit -m "feat: add browser automation tool using Playwright"`

---

### Task 2.4: File Operations Tool

**Files:**
- Modify: `backend/app/tools/file_tool.py` (refactor existing disabled tool)
- Modify: `backend/app/agent/graph.py` (re-enable in `_TOOL_MAP`)

**Implementation:** Refactor existing `file_tool.py` to use factory pattern (close over `user_id`), constrain paths to `/workspace/{user_id}/`, add `list_dir` and `search_files` operations.

**Commit:** `git commit -m "feat: re-enable file operations tool with user workspace isolation"`

---

### Task 2.5: Tool Permission Control

**Files:**
- Create: `backend/app/core/permissions.py`
- Modify: `backend/app/db/models.py` (add `tool_permissions` JSONB to `user_settings`)
- Modify: `backend/app/api/chat.py` (permission check before tool execution)
- Modify: `frontend/src/pages/SettingsPage.vue` (permission UI per tool)
- Create: `backend/alembic/versions/xxxx_tool_permissions.py`

**Design:**

```python
from enum import StrEnum

class ToolPermission(StrEnum):
    AUTO = "auto"    # Execute without asking
    ASK = "ask"      # Pause and ask user for confirmation
    DENY = "deny"    # Never execute

DEFAULT_PERMISSIONS = {
    "rag_search": "auto",
    "web_search": "auto",
    "web_fetch": "auto",
    "datetime": "auto",
    "code_exec": "ask",
    "shell": "ask",
    "browser": "ask",
    "file_read": "auto",
    "file_write": "ask",
}
```

For `ask` permission: SSE emits `{"type": "tool_confirm", "tool": "shell", "args": {...}}`. Frontend shows confirmation dialog. User sends approval/denial via new `POST /api/chat/confirm` endpoint. Agent resumes or skips tool.

**Commit:** `git commit -m "feat: add per-tool permission control (auto/ask/deny)"`

---

## Phase 3: Multi-Channel Access — Gateway + Messaging Platforms

### Task 3.1: Gateway Architecture

**Files:**
- Create: `backend/app/gateway/__init__.py`
- Create: `backend/app/gateway/router.py`
- Create: `backend/app/gateway/session_manager.py`
- Create: `backend/app/gateway/channel_registry.py`
- Create: `backend/app/gateway/models.py`
- Modify: `backend/app/main.py` (register gateway)

**Design:**

```python
# backend/app/gateway/models.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Awaitable, Callable

@dataclass
class GatewayMessage:
    sender_id: str
    channel: str       # "web" | "telegram" | "discord" | "wechat"
    channel_id: str    # channel-specific chat/group ID
    content: str
    attachments: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

class ChannelAdapter(ABC):
    channel_name: str

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send_message(
        self, channel_id: str, content: str, attachments: list | None = None
    ) -> None: ...

    def set_message_handler(
        self, handler: Callable[[GatewayMessage], Awaitable[None]]
    ) -> None: ...
```

```python
# backend/app/gateway/router.py
class GatewayRouter:
    """Routes incoming messages from any channel to the appropriate agent session."""

    async def handle_message(self, msg: GatewayMessage) -> None:
        session = await self.session_manager.get_or_create(msg.sender_id, msg.channel)
        response = await self.process_with_agent(session, msg)
        adapter = self.channel_registry.get(msg.channel)
        await adapter.send_message(msg.channel_id, response)
```

The existing Web SSE chat (`api/chat.py`) becomes the "web" channel adapter.

**Commit:** `git commit -m "feat: add gateway layer for unified multi-channel message routing"`

---

### Task 3.2: Telegram Channel

**Files:**
- Create: `backend/app/channels/__init__.py`
- Create: `backend/app/channels/telegram.py`
- Modify: `backend/pyproject.toml` (add `aiogram` dependency)
- Modify: `backend/app/core/config.py` (add `telegram_bot_token`)
- Modify: `backend/app/main.py` (register Telegram channel on lifespan)

**Implementation:**

```python
# backend/app/channels/telegram.py
import asyncio

from aiogram import Bot, Dispatcher, types

from app.gateway.models import ChannelAdapter, GatewayMessage


class TelegramChannel(ChannelAdapter):
    channel_name = "telegram"

    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)
        self.dp = Dispatcher()
        self._handler = None

    async def start(self) -> None:
        @self.dp.message()
        async def on_message(message: types.Message) -> None:
            if not message.from_user or not message.text:
                return
            gw_msg = GatewayMessage(
                sender_id=str(message.from_user.id),
                channel="telegram",
                channel_id=str(message.chat.id),
                content=message.text,
            )
            if self._handler:
                await self._handler(gw_msg)

        asyncio.create_task(self.dp.start_polling(self.bot))

    async def send_message(self, channel_id: str, content: str, **kwargs) -> None:
        await self.bot.send_message(
            chat_id=int(channel_id), text=content, parse_mode="Markdown"
        )

    async def stop(self) -> None:
        await self.dp.stop_polling()
        await self.bot.session.close()

    def set_message_handler(self, handler) -> None:
        self._handler = handler
```

**Commit:** `git commit -m "feat: add Telegram bot channel adapter"`

---

### Task 3.3: Discord Channel

**Files:**
- Create: `backend/app/channels/discord_channel.py`
- Modify: `backend/pyproject.toml` (add `discord.py` dependency)
- Modify: `backend/app/core/config.py`

**Implementation:** Similar pattern to Telegram, using `discord.py` `Client` with `on_message` event.

**Commit:** `git commit -m "feat: add Discord bot channel adapter"`

---

### Task 3.4: WeChat Channel (Optional)

**Files:**
- Create: `backend/app/channels/wechat.py`

**Implementation:** WeChatFerry-based adapter. Marked as optional/experimental due to ecosystem limitations.

**Commit:** `git commit -m "feat: add WeChat channel adapter (experimental)"`

---

### Task 3.5: DM Security (Pairing Code)

**Files:**
- Create: `backend/app/gateway/security.py`
- Modify: `backend/app/db/models.py` (add `channel_pairings` table)
- Create: `backend/alembic/versions/xxxx_channel_pairings.py`

**Design:**

Pairing flow:
1. Unknown sender sends message, bot replies: "Enter pairing code to start"
2. Admin generates pairing code in web UI (6-digit, 15min expiry)
3. User enters code, pairing confirmed, sender_id linked to user_id
4. Subsequent messages route to that user's agent session

**Commit:** `git commit -m "feat: add pairing code security for messaging channel DMs"`

---

## Phase 4: Multi-Agent Orchestration

### Task 4.1: Session Management

**Files:**
- Create: `backend/app/agent/session.py`
- Modify: `backend/app/db/models.py` (add `agent_sessions` table)
- Create: `backend/alembic/versions/xxxx_agent_sessions.py`

**Design:**

```python
class AgentSession(Base):
    __tablename__ = "agent_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    parent_session_id = Column(UUID(as_uuid=True), ForeignKey("agent_sessions.id"), nullable=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    agent_type = Column(String(20), nullable=False)  # "main" | "sub" | "supervisor"
    status = Column(String(20), nullable=False)  # "active" | "completed" | "aborted"
    context_summary = Column(Text, nullable=True)
    model_provider = Column(String(50), nullable=True)
    model_name = Column(String(100), nullable=True)
    depth = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
```

**Commit:** `git commit -m "feat: add agent session management with parent-child hierarchy"`

---

### Task 4.2: SubAgent Tool

**Files:**
- Create: `backend/app/tools/subagent_tool.py`
- Modify: `backend/app/agent/graph.py`

**Implementation:**

```python
def create_subagent_tool(
    user_id: str,
    parent_session_id: str,
    llm_config,
    depth: int,
):
    MAX_DEPTH = 3

    @tool
    async def spawn_subagent(task: str, model: str | None = None) -> str:
        """Spawn a sub-agent to handle a specific task independently.
        Use for parallel or independent subtasks."""
        if depth >= MAX_DEPTH:
            return "Maximum agent nesting depth reached."
        sub_graph = create_graph(
            provider=llm_config.provider,
            model=model or llm_config.model_name,
            api_key=llm_config.api_key,
            user_id=user_id,
        )
        result = await sub_graph.ainvoke(
            AgentState(
                messages=[
                    SystemMessage(
                        content="You are a focused sub-agent. Complete the task concisely."
                    ),
                    HumanMessage(content=task),
                ]
            )
        )
        return result["messages"][-1].content

    return spawn_subagent
```

**Commit:** `git commit -m "feat: add subagent spawning tool for task decomposition"`

---

### Task 4.3: Context Compression

**Files:**
- Create: `backend/app/agent/compaction.py`
- Modify: `backend/app/api/chat.py` (trigger compaction when context is large)

**Implementation:**

```python
# backend/app/agent/compaction.py
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage


async def compact_messages(
    messages: list[BaseMessage],
    llm,
    max_chars: int = 16000,
) -> list[BaseMessage]:
    """Compress old messages into a summary, keeping recent messages intact."""
    total_chars = sum(len(m.content) for m in messages)
    if total_chars < max_chars:
        return messages

    keep_count = min(10, len(messages))
    to_summarize = messages[:-keep_count]
    to_keep = messages[-keep_count:]

    summary_prompt = (
        "Summarize this conversation concisely, preserving key facts and decisions:\n\n"
    )
    for m in to_summarize:
        summary_prompt += f"{m.type}: {m.content[:500]}\n"

    summary = await llm.ainvoke([HumanMessage(content=summary_prompt)])
    return [
        SystemMessage(content=f"[Previous conversation summary]\n{summary.content}")
    ] + to_keep
```

**Commit:** `git commit -m "feat: add context compression for long conversations"`

---

### Task 4.4: Supervisor Pattern (LangGraph)

**Files:**
- Create: `backend/app/agent/supervisor.py`
- Modify: `backend/app/agent/graph.py` (add supervisor graph variant)

**Design:** A `SupervisorGraph` that receives a complex task, uses an LLM to decompose it into subtasks, spawns subagents for each, and aggregates results.

**Commit:** `git commit -m "feat: add supervisor agent for complex task orchestration"`

---

## Phase 5: Plugin System + Skills Platform

### Task 5.1: Plugin SDK

**Files:**
- Create: `backend/app/plugins/__init__.py`
- Create: `backend/app/plugins/sdk.py`
- Create: `backend/app/plugins/loader.py`
- Create: `backend/app/plugins/registry.py`

**Design:**

```python
# backend/app/plugins/sdk.py
from abc import ABC, abstractmethod


class JarvisPlugin(ABC):
    plugin_id: str
    plugin_name: str
    plugin_version: str = "0.1.0"

    @abstractmethod
    async def on_load(self, api: "PluginAPI") -> None:
        ...

    async def on_unload(self) -> None:
        ...


class PluginAPI:
    """API surface exposed to plugins."""

    def register_tool(self, tool) -> None:
        ...

    def register_channel(self, adapter) -> None:
        ...

    def register_memory_backend(self, backend) -> None:
        ...

    def get_config(self, key: str) -> str | None:
        ...
```

Loader scans `~/.jarvis/plugins/` for Python packages with `jarvis_plugin` entry point.

**Commit:** `git commit -m "feat: add plugin SDK with tool/channel/memory registration"`

---

### Task 5.2: Skills as Markdown

**Files:**
- Create: `backend/app/skills/__init__.py`
- Create: `backend/app/skills/loader.py`
- Create: `backend/app/skills/registry.py`
- Modify: `backend/app/agent/persona.py` (inject available skills into system prompt)

**Design:**

Skill file format (YAML frontmatter + Markdown body):
```yaml
---
name: weather-lookup
description: Look up current weather for any city
triggers:
  - weather
  - forecast
  - temperature
---
```

Loader scans `~/.jarvis/skills/` and project `skills/` directories. Skills listed in system prompt. Agent reads full skill content when triggered.

**Commit:** `git commit -m "feat: add Markdown-based skills system for agent behavior customization"`

---

### Task 5.3: Cron / Scheduled Tasks

**Files:**
- Create: `backend/app/scheduler/__init__.py`
- Create: `backend/app/scheduler/manager.py`
- Create: `backend/app/tools/cron_tool.py`
- Modify: `backend/pyproject.toml` (add `apscheduler` dependency)
- Modify: `backend/app/db/models.py` (add `cron_jobs` table)

**Implementation:** APScheduler with async support. `cron_jobs` table stores user-defined schedules. Each trigger creates a new agent session.

**Commit:** `git commit -m "feat: add cron/scheduled task support for agent"`

---

### Task 5.4: Webhook System

**Files:**
- Create: `backend/app/api/webhooks.py`
- Modify: `backend/app/db/models.py` (add `webhooks` table)
- Modify: `backend/app/main.py` (register webhooks router)

**Design:**

```python
@router.post("/{webhook_id}")
async def handle_webhook(webhook_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    webhook = await db.get(Webhook, webhook_id)
    if not webhook:
        raise HTTPException(404)
    payload = await request.json()
    # Create agent session with webhook.prompt_template.format(payload)
```

**Commit:** `git commit -m "feat: add webhook system for external event-triggered agent sessions"`

---

### Task 5.5: MCP Client Integration

**Files:**
- Create: `backend/app/mcp/__init__.py`
- Create: `backend/app/mcp/client.py`
- Modify: `backend/pyproject.toml` (add `mcp` dependency)
- Modify: `backend/app/agent/graph.py` (register MCP tools dynamically)

**Design:**

```python
# backend/app/mcp/client.py
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def connect_mcp_server(server_config: dict) -> list:
    """Connect to an MCP server and convert its tools to LangGraph tools."""
    server_params = StdioServerParameters(
        command=server_config["command"],
        args=server_config.get("args", []),
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return [mcp_tool_to_langchain(t, session) for t in tools.tools]
```

**Commit:** `git commit -m "feat: add MCP client integration for external tool servers"`

---

## Phase 6: Terminal Experience — Voice + Canvas + Mobile

### Task 6.1: TTS Voice Reply

**Files:**
- Create: `backend/app/api/tts.py`
- Modify: `backend/pyproject.toml` (add `edge-tts` dependency)
- Modify: `backend/app/main.py` (register TTS router)
- Modify: `frontend/src/pages/ChatPage.vue` (add play button per AI message)

**Implementation:**

```python
# backend/app/api/tts.py
import edge_tts
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/tts", tags=["tts"])


class TTSRequest(BaseModel):
    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"


@router.post("/synthesize")
async def synthesize(body: TTSRequest) -> StreamingResponse:
    communicate = edge_tts.Communicate(body.text, body.voice)

    async def generate():
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    return StreamingResponse(generate(), media_type="audio/mpeg")
```

**Commit:** `git commit -m "feat: add TTS voice reply using Edge TTS"`

---

### Task 6.2: Voice Input

**Files:**
- Modify: `frontend/src/pages/ChatPage.vue` (add microphone button, Web Speech API)

**Implementation:** Use `webkitSpeechRecognition` / `SpeechRecognition` API for zero-cost browser-native STT. Fallback message if not supported.

**Commit:** `git commit -m "feat: add voice input using Web Speech API"`

---

### Task 6.3: Live Canvas

**Files:**
- Create: `backend/app/tools/canvas_tool.py`
- Create: `frontend/src/components/CanvasViewer.vue`
- Modify: `frontend/src/pages/ChatPage.vue` (embed CanvasViewer)

**Implementation:**

Agent tool `canvas_render(html: str)` sends HTML/CSS/JS via SSE event `{"type": "canvas", "html": "..."}`. Frontend renders in a sandboxed iframe with `srcdoc`.

**Commit:** `git commit -m "feat: add live canvas for agent-driven interactive UI"`

---

### Task 6.4: Mobile Adaptation

**Implementation:**
- Phase A: Responsive CSS for ChatPage (media queries for less than 768px)
- Phase B: PWA manifest + service worker for installability
- Phase C (optional): Capacitor wrapper for native app distribution

**Commit:** `git commit -m "feat: add responsive design and PWA support for mobile"`

---

### Task 6.5: Usage Dashboard

**Files:**
- Modify: `backend/app/db/models.py` (add `token_usage` table)
- Create: `backend/app/api/usage.py`
- Create: `frontend/src/pages/UsagePage.vue`
- Modify: `frontend/src/router/index.ts` (add `/usage` route)
- Modify: `backend/app/api/chat.py` (record token usage after each LLM call)
- Create: `backend/alembic/versions/xxxx_token_usage.py`

**Design:**

```python
class TokenUsage(Base):
    __tablename__ = "token_usage"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), nullable=True)
    model_provider = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    estimated_cost = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

API: `GET /api/usage?period=day|week|month` returns aggregated stats.
Frontend: Chart.js or ECharts for visualization.

**Commit:** `git commit -m "feat: add token usage tracking and usage dashboard"`

---

## Dependency Graph

```
Phase 1 (no deps) -----+---> Phase 2 ---> Phase 4
                        |
                        +---> Phase 3
                        |
                        +---> Phase 6 (partial: TTS, Voice, Usage)

Phase 2 + Phase 3 ----------> Phase 5
```

## Execution Order (Recommended)

1. **Phase 1**: Tasks 1.1, 1.2, 1.3, 1.4, 1.5
2. **Phase 2**: Tasks 2.1, 2.2, 2.3, 2.4, 2.5
3. **Phase 3**: Tasks 3.1, 3.2, 3.3, 3.5 (3.4 optional)
4. **Phase 6**: Tasks 6.5, 6.1, 6.2 (can interleave with Phase 2-3)
5. **Phase 4**: Tasks 4.1, 4.2, 4.3, 4.4
6. **Phase 5**: Tasks 5.1, 5.2, 5.3, 5.4, 5.5
