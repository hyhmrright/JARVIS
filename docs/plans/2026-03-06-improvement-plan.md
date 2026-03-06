# JARVIS Improvement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 通过三个顺序 PR 解决 JARVIS 的性能瓶颈、代码质量问题和功能缺口。

**Architecture:** PR-B 先合并，PR-A 在 PR-B 合并后从更新的 `dev` 创建（因为 PR-B 和 PR-A 都修改 `chat.py`，不能并行），PR-A 合并后开始 PR-C。PR-B 改 `router.py` + `chat.py`（complex 分支），PR-A 改 `agent_runner.py` + 重构 `chat.py` + 补测试，PR-C 在干净的 `chat.py` 基础上增加标题生成、多轮 RAG、AgentSession 写入。

**Tech Stack:** Python 3.13, FastAPI, LangGraph, pytest-asyncio, Vue 3 + TypeScript + Pinia

---

## PR-B：性能优化

**分支：** `feature/perf-routing`（从 `dev` 创建）

---

### Task B-1：规则优先路由（router.py）

**Files:**
- Modify: `backend/app/agent/router.py`
- Modify: `backend/tests/agent/test_router.py`

**Step 1: 写失败测试**

在 `backend/tests/agent/test_router.py` 末尾追加：

```python
@pytest.mark.anyio
async def test_rule_based_classify_code_keywords():
    """规则层对代码关键词直接返回 code，无需 LLM。"""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        result = await classify_task(
            "帮我写一个 Python function 解析 CSV",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert result == "code"
        mock_get_llm.assert_not_called()  # 规则命中，LLM 不被调用


@pytest.mark.anyio
async def test_rule_based_classify_research_keywords():
    """规则层对调研关键词直接返回 research。"""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        result = await classify_task(
            "帮我搜索一下最新的 AI 论文",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert result == "research"
        mock_get_llm.assert_not_called()


@pytest.mark.anyio
async def test_rule_based_classify_writing_keywords():
    """规则层对写作关键词直接返回 writing。"""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        result = await classify_task(
            "帮我写一篇关于量子计算的文章",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert result == "writing"
        mock_get_llm.assert_not_called()


@pytest.mark.anyio
async def test_rule_based_classify_short_message_is_simple():
    """短消息（< 50 字且无动作词）直接返回 simple。"""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        result = await classify_task(
            "你好",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert result == "simple"
        mock_get_llm.assert_not_called()


@pytest.mark.anyio
async def test_rule_based_classify_falls_through_to_llm():
    """规则层未命中时，仍调用 LLM 分类。"""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="complex"))
        mock_get_llm.return_value = mock_llm

        result = await classify_task(
            "请帮我协调团队的多个跨部门项目，并生成汇报材料",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert result == "complex"
        mock_get_llm.assert_called_once()
```

**Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/agent/test_router.py -v -k "rule_based"
```

预期：FAIL（`_rule_based_classify` 不存在）

**Step 3: 实现 `_rule_based_classify`**

在 `backend/app/agent/router.py` 中，在 `_ROUTER_PROMPT` 定义之后、`classify_task` 之前插入：

```python
_CODE_KEYWORDS = frozenset(
    {"代码", "写代码", "debug", "调试", "实现", "function", "class", "脚本",
     "script", "程序", "编写", "bug", "报错", "error", "fix"}
)
_RESEARCH_KEYWORDS = frozenset(
    {"搜索", "查找", "调研", "research", "找一下", "查一下", "搜一下",
     "了解", "资料", "信息", "新闻", "文献", "论文"}
)
_WRITING_KEYWORDS = frozenset(
    {"写文章", "写一篇", "翻译", "总结", "润色", "修改文章", "起草",
     "文案", "copywriting", "draft", "summarize", "translate"}
)
_ACTION_WORDS = frozenset(
    {"写", "做", "帮", "实现", "创建", "生成", "分析", "解释",
     "write", "create", "build", "make", "analyze", "explain"}
)


def _rule_based_classify(message: str) -> str | None:
    """Quick keyword-based classification. Returns None if no rule matches."""
    lower = message.lower()

    if any(kw in lower for kw in _CODE_KEYWORDS):
        return "code"
    if any(kw in lower for kw in _RESEARCH_KEYWORDS):
        return "research"
    if any(kw in lower for kw in _WRITING_KEYWORDS):
        return "writing"
    # Short message with no clear action → simple
    if len(message) < 50 and not any(w in lower for w in _ACTION_WORDS):
        return "simple"
    return None
```

然后修改 `classify_task` 函数，在 `try:` 块开头增加规则层调用：

```python
async def classify_task(
    message: str,
    *,
    provider: str,
    model: str,
    api_key: str,
) -> str:
    # Fast path: rule-based classification (no LLM call)
    rule_result = _rule_based_classify(message)
    if rule_result is not None:
        logger.info("router_rule_classified", label=rule_result)
        return rule_result

    # Slow path: LLM fallback
    try:
        llm = get_llm(provider, model, api_key)
        # ... 保留现有代码不变
```

**Step 4: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/agent/test_router.py -v
```

预期：4 个原有测试 + 5 个新测试 = 共 9 个测试 PASS

**Step 5: 静态检查**

```bash
cd backend && uv run ruff check --fix app/agent/router.py && uv run ruff format app/agent/router.py
cd backend && uv run mypy app/agent/router.py
```

**Step 6: Commit**

```bash
git add backend/app/agent/router.py backend/tests/agent/test_router.py
git commit -m "perf(router): add rule-based fast path to skip LLM for obvious classifications"
```

---

### Task B-2：Supervisor 流式体验改善（chat.py）

**Files:**
- Modify: `backend/app/api/chat.py:289-316`

**Step 1: 修改 chat.py 的 complex 分支**

> 注意：无需先写测试。`_format_sse` 已在 `chat.py` 中定义且被 `test_chat_routing.py` 导入测试过，此任务只需修改 `generate()` 内 `route == "complex"` 分支的行为。

找到 `backend/app/api/chat.py` 中 `route == "complex"` 的分支（约第 290 行）：

```python
# 修改前：
if route == "complex":
    supervisor = create_supervisor_graph(...)
    final_state = await supervisor.ainvoke(
        SupervisorState(messages=lc_messages)
    )
    msgs = final_state.get("messages", [])
    if msgs:
        last_ai_msg = msgs[-1]
        full_content = str(getattr(last_ai_msg, "content", ""))
        if full_content:
            yield _format_sse(
                {"type": "delta", "delta": full_content, "content": full_content}
            )

# 修改后：
if route == "complex":
    yield _format_sse({"type": "status", "message": "正在规划复杂任务..."})
    supervisor = create_supervisor_graph(...)
    final_state = await supervisor.ainvoke(
        SupervisorState(messages=lc_messages)
    )
    msgs = final_state.get("messages", [])
    if msgs:
        last_ai_msg = msgs[-1]
        full_content = str(getattr(last_ai_msg, "content", ""))
        if full_content:
            # 分块输出，每 50 字一个 delta，让用户感知到内容在流动
            chunk_size = 50
            for i in range(0, len(full_content), chunk_size):
                chunk = full_content[i : i + chunk_size]
                yield _format_sse(
                    {
                        "type": "delta",
                        "delta": chunk,
                        "content": full_content[: i + chunk_size],
                    }
                )
```

**Step 2: 运行测试**

```bash
cd backend && uv run pytest tests/api/test_chat_routing.py -v
```

预期：所有现有测试 PASS（改动仅在 `generate()` 内部，不影响已有的 `_format_sse` 和 `_build_expert_graph` 测试）

**Step 3: 静态检查**

```bash
cd backend && uv run ruff check --fix app/api/chat.py && uv run ruff format app/api/chat.py
cd backend && uv run mypy app/api/chat.py
```

**Step 4: Commit**

```bash
git add backend/app/api/chat.py
git commit -m "feat(chat): emit status event + chunked output for complex supervisor route"
```

---

### Task B-3：PR-B 验证 & Push

**Step 1: 完整测试套件**

```bash
cd backend && uv run pytest tests/ -v
cd frontend && bun run type-check
```

**Step 2: Push**

```bash
git push -u origin feature/perf-routing
```

---

## PR-A：内部清洁

**分支：** `fix/internal-cleanup`（从合并 PR-B 后的 `dev` 创建，因 PR-B Task B-2 也修改了 `chat.py`）

---

### Task A-1：改善 agent_runner.py 错误提示

**Files:**
- Modify: `backend/app/gateway/agent_runner.py:104-106`
- Create: `backend/tests/gateway/test_gateway_runner.py`

注意：`agent_runner.py` 中的 `run_agent_for_user()` 已有 try/except，只需改英文错误为中文。
测试放在新文件 `test_gateway_runner.py`，而非已有的 `test_gateway_agent.py`（后者专门测试 `GatewayRouter._run_agent`，函数不同）。

**Step 1: 写失败测试**

新建 `backend/tests/gateway/test_gateway_runner.py`：

```python
"""Tests for run_agent_for_user in gateway/agent_runner.py."""
from unittest.mock import patch

import pytest

from app.gateway.agent_runner import run_agent_for_user


@pytest.mark.asyncio
async def test_run_agent_for_user_returns_chinese_error_on_exception():
    """run_agent_for_user 异常时返回中文友好提示，不返回英文。"""
    with patch(
        "app.gateway.agent_runner.AsyncSessionLocal",
        side_effect=RuntimeError("DB down"),
    ):
        result = await run_agent_for_user("00000000-0000-0000-0000-000000000001", "test")

    assert "抱歉" in result or "错误" in result
    assert "Agent execution failed" not in result  # 不再返回英文
```

**Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/gateway/test_gateway_runner.py -v
```

预期：FAIL（当前返回英文 "Agent execution failed."）

**Step 3: 修改 agent_runner.py**

将 `backend/app/gateway/agent_runner.py` 第 104-106 行：

```python
    except Exception:
        logger.exception("agent_runner_error", user_id=user_id)
        return "Agent execution failed."
```

改为：

```python
    except Exception:
        logger.exception("agent_runner_error", user_id=user_id)
        return "抱歉，处理请求时出现错误，请稍后重试。"
```

**Step 4: 运行测试**

```bash
cd backend && uv run pytest tests/gateway/test_gateway_runner.py tests/gateway/test_gateway_agent.py -v
```

预期：所有测试 PASS

**Step 5: Commit**

```bash
git add backend/app/gateway/agent_runner.py backend/tests/gateway/test_gateway_runner.py
git commit -m "fix(gateway): localize error message in run_agent_for_user to Chinese"
```

---

### Task A-2：拆解 chat.py 的 generate() 函数

**Files:**
- Modify: `backend/app/api/chat.py`

这是最大的重构任务。目标是把 `chat_stream()` 和 `generate()` 合计 180+ 行拆成职责单一的私有函数。

**Step 1: 理解现有结构（先读代码）**

阅读 `backend/app/api/chat.py` 第 192-373 行，记住：
- `chat_stream()` (193-373)：HTTP 处理器，包含 DB 查询、历史加载、RAG 注入，以及内嵌 `generate()` 函数
- `generate()` (251-372)：内嵌异步生成器，负责消息压缩、工具加载、路由、SSE 流、消息保存

**Step 2: 提取 `_load_tools()`**

在 `chat.py` 中，在 `chat_stream` 函数定义**之前**（约第 192 行）新增模块级私有函数：

```python
async def _load_tools(
    llm_enabled: list[str] | None,
) -> tuple[list, list | None]:
    """Load MCP tools and plugin tools based on enabled_tools config.

    Returns (mcp_tools, plugin_tools).
    """
    mcp_tools: list = []
    if llm_enabled is None or "mcp" in llm_enabled:
        from app.tools.mcp_client import create_mcp_tools, parse_mcp_configs

        mcp_tools = await create_mcp_tools(
            parse_mcp_configs(settings.mcp_servers_json)
        )

    plugin_tools: list | None = None
    if llm_enabled is None or "plugin" in llm_enabled:
        plugin_tools = plugin_registry.get_all_tools() or None

    return mcp_tools, plugin_tools
```

**Step 3: 提取 `_save_response()`**

在 `_load_tools` 之后新增：

```python
async def _save_response(
    *,
    conv_id: uuid.UUID,
    full_content: str,
    provider: str,
    model_name: str,
    last_ai_msg: object | None,
) -> None:
    """Persist the AI response to the database and sync to markdown."""
    tokens_in, tokens_out = _extract_token_counts(last_ai_msg)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            session.add(
                Message(
                    conversation_id=conv_id,
                    role="ai",
                    content=full_content,
                    model_provider=provider,
                    model_name=model_name,
                    tokens_input=tokens_in,
                    tokens_output=tokens_out,
                )
            )
    logger.info(
        "chat_stream_completed",
        conv_id=str(conv_id),
        response_chars=len(full_content),
    )
    asyncio.create_task(sync_conversation_to_markdown(conv_id))
```

**Step 4: 在 generate() 中使用新函数**

将 `generate()` 内部的工具加载代码替换为 `_load_tools()` 调用：

```python
# 替换前（约第 262-272 行）：
mcp_tools: list = []
if llm.enabled_tools is None or "mcp" in llm.enabled_tools:
    from app.tools.mcp_client import create_mcp_tools, parse_mcp_configs
    mcp_tools = await create_mcp_tools(...)
plugin_tools: list | None = None
if llm.enabled_tools is None or "plugin" in llm.enabled_tools:
    plugin_tools = plugin_registry.get_all_tools() or None

# 替换后：
mcp_tools, plugin_tools = await _load_tools(llm.enabled_tools)
```

将 `finally` 块中的保存逻辑替换为 `_save_response()` 调用：

```python
# 替换前（约第 344-371 行）：
finally:
    if full_content:
        try:
            tokens_in, tokens_out = _extract_token_counts(last_ai_msg)
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    session.add(Message(...))
            logger.info(...)
            asyncio.create_task(sync_conversation_to_markdown(conv_id))
        except Exception:
            logger.exception("failed_to_save_partial_response", ...)

# 替换后：
finally:
    if full_content:
        try:
            await _save_response(
                conv_id=conv_id,
                full_content=full_content,
                provider=llm.provider,
                model_name=llm.model_name,
                last_ai_msg=last_ai_msg,
            )
        except Exception:
            logger.exception("failed_to_save_partial_response", conv_id=str(conv_id))
```

**Step 5: 静态检查**

```bash
cd backend && uv run ruff check --fix app/api/chat.py && uv run ruff format app/api/chat.py
cd backend && uv run mypy app/api/chat.py
cd backend && uv run pytest --collect-only -q  # 验证 import 正常
```

**Step 6: 运行完整测试**

```bash
cd backend && uv run pytest tests/ -v
```

预期：所有现有测试 PASS（纯重构，无行为变更）

**Step 7: Commit**

```bash
git add backend/app/api/chat.py
git commit -m "refactor(chat): extract _load_tools and _save_response from generate()"
```

---

### Task A-3：新增 test_chat.py API 集成测试

**Files:**
- Create: `backend/tests/api/test_chat.py`

**Step 1: 理解 conftest**

先读 `backend/tests/conftest.py` 了解现有 `auth_client` fixture 的结构。

**Step 2: 写测试文件**

新建 `backend/tests/api/test_chat.py`：

```python
"""Integration tests for POST /api/chat/stream.

All LangGraph graphs are mocked — no real LLM calls are made.
"""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_sse(payload: dict) -> str:
    return "data: " + json.dumps(payload) + "\n\n"


def _make_stream(*payloads: dict) -> AsyncGenerator[str, None]:
    """Build a fake async generator that yields SSE events."""

    async def _gen() -> AsyncGenerator[str, None]:
        for p in payloads:
            yield _make_sse(p)

    return _gen()


@pytest.mark.anyio
async def test_chat_stream_requires_auth(client):
    """Unauthenticated requests return 401."""
    resp = await client.post(
        "/api/chat/stream",
        json={"conversation_id": "00000000-0000-0000-0000-000000000001", "content": "hi"},
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_chat_stream_unknown_conversation_returns_404(auth_client):
    """A conversation_id that belongs to another user returns 404."""
    resp = await auth_client.post(
        "/api/chat/stream",
        json={
            "conversation_id": "00000000-0000-0000-0000-000000000099",
            "content": "hello",
        },
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_chat_stream_simple_route_returns_delta(auth_client):
    """A simple message produces a delta SSE event."""
    # Create a conversation first
    conv_resp = await auth_client.post("/api/conversations", json={"title": "Test"})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    # Mock: router classifies as "simple", graph yields a delta
    fake_chunk = {"llm": {"messages": [MagicMock(
        content="Hello!",
        tool_calls=[],
        usage_metadata={"input_tokens": 10, "output_tokens": 5},
    )]}}

    async def fake_astream(state):
        yield fake_chunk

    mock_graph = MagicMock()
    mock_graph.astream = fake_astream

    with (
        patch("app.api.chat.classify_task", return_value="simple"),
        patch("app.api.chat._load_tools", return_value=([], None)),
        patch("app.api.chat._build_expert_graph", return_value=mock_graph),
        patch("app.api.chat._save_response"),
    ):
        resp = await auth_client.post(
            "/api/chat/stream",
            json={"conversation_id": conv_id, "content": "hi"},
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    # At minimum a routing event should appear
    body = resp.text
    events = [
        json.loads(line[6:])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    assert any(e.get("type") == "routing" for e in events)
```

**Step 3: 运行测试**

```bash
cd backend && uv run pytest tests/api/test_chat.py -v
```

**Step 4: 扩展 test_conversations.py**

在 `backend/tests/api/test_conversations.py` 末尾追加：

```python
async def test_get_conversation_messages(auth_client):
    """GET /api/conversations/{id}/messages 返回消息列表。"""
    conv = await auth_client.post("/api/conversations", json={"title": "Msgs"})
    conv_id = conv.json()["id"]
    resp = await auth_client.get(f"/api/conversations/{conv_id}/messages")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_delete_nonexistent_conversation_returns_404(auth_client):
    """删除不存在的会话返回 404。"""
    resp = await auth_client.delete(
        "/api/conversations/00000000-0000-0000-0000-000000000099"
    )
    assert resp.status_code == 404
```

**Step 5: 静态检查 + 运行测试**

```bash
cd backend && uv run ruff check --fix tests/api/ && uv run ruff format tests/api/
cd backend && uv run pytest tests/api/ -v
```

**Step 6: Commit**

```bash
git add backend/tests/api/test_chat.py backend/tests/api/test_conversations.py
git commit -m "test(api): add chat stream integration tests and extend conversations tests"
```

---

### Task A-4：PR-A 验证 & Push

**Step 1: 完整验证**

```bash
cd backend && uv run pytest tests/ -v
cd backend && uv run mypy app
cd frontend && bun run type-check
pre-commit run --all-files
```

**Step 2: Push**

```bash
git push -u origin fix/internal-cleanup
```

---

## PR-C：功能完善

**分支：** `feature/ux-improvements`（从合并后的 `dev` 创建，确保包含 PR-A 的改动）

---

### Task C-1：对话标题自动生成（后端）

**Files:**
- Create: `backend/app/agent/title_generator.py`
- Modify: `backend/app/api/chat.py` — `_save_response()`

**Step 1: 写失败测试**

新建 `backend/tests/agent/test_title_generator.py`：

```python
"""Tests for conversation title generator."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.title_generator import generate_title


@pytest.mark.anyio
async def test_generate_title_returns_short_string():
    """generate_title 应返回 ≤ 10 字的标题。"""
    with patch("app.agent.title_generator.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="Python CSV 解析器")
        )
        mock_get_llm.return_value = mock_llm

        result = await generate_title(
            user_message="帮我写一个 Python function 解析 CSV",
            ai_reply="好的，这里是代码...",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert isinstance(result, str)
        assert len(result) <= 20  # 允许稍微超出，LLM 可能不完全遵守


@pytest.mark.anyio
async def test_generate_title_falls_back_on_error():
    """LLM 报错时返回 None，不抛异常。"""
    with patch("app.agent.title_generator.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))
        mock_get_llm.return_value = mock_llm

        result = await generate_title(
            user_message="任何内容",
            ai_reply="回复",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert result is None
```

**Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/agent/test_title_generator.py -v
```

预期：FAIL（模块不存在）

**Step 3: 创建 title_generator.py**

新建 `backend/app/agent/title_generator.py`：

```python
"""Generates a short conversation title from the first exchange."""
from __future__ import annotations

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm import get_llm

logger = structlog.get_logger(__name__)

_TITLE_PROMPT = """\
Based on this conversation exchange, generate a concise title in the same language as the user's message.
The title must be ≤ 10 characters (Chinese) or ≤ 6 words (English).
Reply with ONLY the title text. No punctuation, no quotes."""


async def generate_title(
    *,
    user_message: str,
    ai_reply: str,
    provider: str,
    model: str,
    api_key: str,
) -> str | None:
    """Generate a short conversation title. Returns None on any error."""
    try:
        llm = get_llm(provider, model, api_key)
        context = f"User: {user_message[:200]}\nAssistant: {ai_reply[:200]}"
        response = await llm.ainvoke(
            [
                SystemMessage(content=_TITLE_PROMPT),
                HumanMessage(content=context),
            ]
        )
        title = response.content
        return (title if isinstance(title, str) else "").strip()[:50] or None
    except Exception:
        logger.warning("title_generation_failed", exc_info=True)
        return None
```

**Step 4: 修改 `_save_response()` 以触发标题生成**

在 `backend/app/api/chat.py` 中，修改 `_save_response()` 签名和内部逻辑：

```python
async def _save_response(
    *,
    conv_id: uuid.UUID,
    full_content: str,
    provider: str,
    model_name: str,
    api_key: str,
    last_ai_msg: object | None,
    user_message: str = "",
    is_first_exchange: bool = False,
    title_queue: asyncio.Queue | None = None,
) -> None:
    """Persist the AI response to DB; optionally trigger title generation on first exchange.

    Returns the generated title string if one was created, otherwise None.
    Title generation is done BEFORE opening the DB transaction to avoid holding
    an open transaction across a long-running LLM network call.
    """
    tokens_in, tokens_out = _extract_token_counts(last_ai_msg)

    # Generate title outside the DB transaction (LLM call can take seconds)
    new_title: str | None = None
    if is_first_exchange and user_message:
        from app.agent.title_generator import generate_title

        new_title = await generate_title(
            user_message=user_message,
            ai_reply=full_content,
            provider=provider,
            model=model_name,
            api_key=api_key,
        )

    async with AsyncSessionLocal() as session:
        async with session.begin():
            session.add(
                Message(
                    conversation_id=conv_id,
                    role="ai",
                    content=full_content,
                    model_provider=provider,
                    model_name=model_name,
                    tokens_input=tokens_in,
                    tokens_output=tokens_out,
                )
            )
            if new_title:
                from sqlalchemy import update

                await session.execute(
                    update(Conversation)
                    .where(Conversation.id == conv_id)
                    .values(title=new_title)
                )

    logger.info(
        "chat_stream_completed",
        conv_id=str(conv_id),
        response_chars=len(full_content),
    )
    asyncio.create_task(sync_conversation_to_markdown(conv_id))
    return new_title  # caller decides whether to emit SSE event
```

在 `generate()` 的 finally 块中传入新参数，并在 `generate()` 结束前 yield title_updated 事件：

```python
# finally 块中（_save_response 现在直接返回 new_title，无需 Queue）
new_title = await _save_response(
    conv_id=conv_id,
    full_content=full_content,
    provider=llm.provider,
    model_name=llm.model_name,
    api_key=llm.api_key,
    last_ai_msg=last_ai_msg,
    user_message=body_content,           # 从外部传入
    is_first_exchange=is_first_exchange, # len(lc_messages) == 2（system + human）时为 True
)
if new_title:
    yield _format_sse({"type": "title_updated", "title": new_title})
```

**Step 5: 运行测试**

```bash
cd backend && uv run pytest tests/agent/test_title_generator.py tests/api/ -v
cd backend && uv run ruff check --fix app/ && uv run ruff format app/
cd backend && uv run mypy app/
```

**Step 6: Commit**

```bash
git add backend/app/agent/title_generator.py backend/app/api/chat.py backend/tests/agent/test_title_generator.py
git commit -m "feat(chat): auto-generate conversation title after first exchange"
```

---

### Task C-2：前端处理 title_updated 事件

**Files:**
- Modify: `frontend/src/stores/chat.ts`

**Step 1: 在 sendMessage 的 SSE 解析中增加 title_updated 处理**

在 `frontend/src/stores/chat.ts` 约第 131 行，找到以下代码：

```typescript
if (data.type === "routing") {
  this.routingAgent = data.agent;
} else if (data.type === "approval_required") {
```

在 `this.routingAgent = data.agent;` 这一行**之后**、`} else if (data.type === "approval_required")` **之前**，插入新的 else if 分支：

```typescript
if (data.type === "routing") {
  this.routingAgent = data.agent;
} else if (data.type === "title_updated") {
  // Update the conversation title in the sidebar in real time
  const conv = this.conversations.find(c => c.id === this.currentConvId);
  if (conv) {
    conv.title = data.title;
  }
} else if (data.type === "approval_required") {
```

注意：不要放在 `approval_required` 分支之后，那个分支以 `return` 结束，后续 else if 不会执行。

**Step 2: 类型检查**

```bash
cd frontend && bun run type-check
```

**Step 3: Commit**

```bash
git add frontend/src/stores/chat.ts
git commit -m "feat(frontend): handle title_updated SSE event to refresh conversation title"
```

---

### Task C-3：多轮对话 RAG 检索

**Files:**
- Modify: `backend/app/rag/retriever.py`
- Modify: `backend/app/api/chat.py`

**Step 1: 写失败测试**

在 `backend/tests/api/test_chat_rag.py` 末尾追加（需先在文件顶部补充 import：`from unittest.mock import AsyncMock, patch` 和 `import pytest`）：

```python
@pytest.mark.anyio
async def test_rag_uses_score_threshold_in_qdrant_query():
    """score_threshold 应传入 Qdrant 查询，而非在 Python 层过滤。"""
    from app.rag.retriever import retrieve_context

    mock_client = AsyncMock()
    mock_client.search = AsyncMock(return_value=[])

    with (
        patch("app.rag.retriever.get_qdrant_client", AsyncMock(return_value=mock_client)),
        patch("app.rag.retriever.get_embedder") as mock_embedder,
    ):
        mock_embedder.return_value.aembed_query = AsyncMock(return_value=[0.1] * 1536)
        await retrieve_context("test query", "user-123", "fake-key")

    # Verify score_threshold was passed to Qdrant search
    call_kwargs = mock_client.search.call_args.kwargs
    assert "score_threshold" in call_kwargs
    assert call_kwargs["score_threshold"] == 0.7
```

**Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/api/test_chat_rag.py -v -k "score_threshold"
```

预期：FAIL（score_threshold 目前在 Python 层过滤）

**Step 3: 修改 retriever.py**

在 `backend/app/rag/retriever.py` 中修改 `retrieve_context()`：

```python
# 修改前（第 38-42 行 search 调用 + 第 52-60 行 return）：
hits = await client.search(  # type: ignore[attr-defined]
    collection_name=user_collection_name(user_id),
    query_vector=query_vec,
    limit=top_k,
)
# ...
return [
    RetrievedChunk(
        document_name=hit.payload.get("doc_name", "Unknown document"),
        content=hit.payload.get("text", ""),
        score=hit.score,
    )
    for hit in hits
    if hit.score >= score_threshold and hit.payload  # Python 层过滤
]

# 修改后：
hits = await client.search(  # type: ignore[attr-defined]
    collection_name=user_collection_name(user_id),
    query_vector=query_vec,
    limit=top_k,
    score_threshold=score_threshold,  # 移到 Qdrant 层
)
# ...
return [
    RetrievedChunk(
        document_name=hit.payload.get("doc_name", "Unknown document"),
        content=hit.payload.get("text", ""),
        score=hit.score,
    )
    for hit in hits
    if hit.payload  # 只保留 payload 非空检查
]
```

**Step 4: 修改 chat.py 支持多轮 RAG**

在 `backend/app/api/chat.py` 的 `chat_stream()` 中，`maybe_inject_rag_context` 调用处（约第 234 行），将查询构建改为包含上一条 AI 消息：

```python
# 修改前：
lc_messages = await maybe_inject_rag_context(
    lc_messages, body.content, str(user.id), openai_key
)

# 修改后（注意：以下代码在 chat_stream() 函数体内，需保持 4 空格缩进）：
    # Build enriched query: current message + last AI reply for better recall
    last_ai_content = next(
        (msg.content for msg in reversed(lc_messages) if isinstance(msg, AIMessage)),
        "",
    )
    rag_query = (
        f"{body.content}\n{last_ai_content[:200]}" if last_ai_content else body.content
    )
    lc_messages = await maybe_inject_rag_context(
        lc_messages, rag_query, str(user.id), openai_key
    )
```

**Step 5: 运行测试**

```bash
cd backend && uv run pytest tests/api/test_chat_rag.py tests/agent/ -v
cd backend && uv run ruff check --fix app/ && uv run ruff format app/
cd backend && uv run mypy app/
```

**Step 6: Commit**

```bash
git add backend/app/rag/retriever.py backend/app/api/chat.py backend/tests/api/test_chat_rag.py
git commit -m "feat(rag): push score_threshold to Qdrant layer and enrich multi-turn query"
```

---

### Task C-4：AgentSession 状态写入

**Files:**
- Modify: `backend/app/api/chat.py` — `generate()` 和 `_save_response()`

**Step 1: 写测试验证 AgentSession 被写入**

在 `backend/tests/api/test_chat.py` 中追加：

```python
@pytest.mark.anyio
async def test_chat_stream_creates_agent_session(auth_client):
    """chat stream 完成后 agent_sessions 表应有 completed 记录。"""
    from app.db.models import AgentSession
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select

    conv_resp = await auth_client.post("/api/conversations", json={"title": "Session Test"})
    conv_id = conv_resp.json()["id"]

    fake_chunk = {"llm": {"messages": [MagicMock(
        content="Done",
        tool_calls=[],
        usage_metadata=None,
    )]}}

    async def fake_astream(state):
        yield fake_chunk

    mock_graph = MagicMock()
    mock_graph.astream = fake_astream

    with (
        patch("app.api.chat.classify_task", return_value="simple"),
        patch("app.api.chat._load_tools", return_value=([], None)),
        patch("app.api.chat._build_expert_graph", return_value=mock_graph),
    ):
        await auth_client.post(
            "/api/chat/stream",
            json={"conversation_id": conv_id, "content": "test"},
        )

    async with AsyncSessionLocal() as db:
        session = await db.scalar(
            select(AgentSession).where(
                AgentSession.conversation_id == conv_id
            )
        )
    assert session is not None
    assert session.status == "completed"
```

**Step 2: 修改 generate() 写入 AgentSession**

在 `generate()` 函数开头（压缩消息之后）插入 AgentSession 创建：

首先，将 `AgentSession` 加入 `chat.py` 顶部已有的模型 import（第 24 行）：

```python
# 修改前：
from app.db.models import Conversation, Message, User
# 修改后：
from app.db.models import AgentSession, Conversation, Message, User
```

然后，在 `generate()` 函数开头（压缩消息之后）插入 AgentSession 创建：

```python
# 在 generate() 开头
agent_session_id: uuid.UUID | None = None
try:
    async with AsyncSessionLocal() as _init_session:
        async with _init_session.begin():
            ag_sess = AgentSession(
                conversation_id=conv_id,
                agent_type="main",
                status="active",
            )
            _init_session.add(ag_sess)
            await _init_session.flush()
            agent_session_id = ag_sess.id
except Exception:
    logger.warning("agent_session_create_failed", exc_info=True)
```

在 `_save_response()` 中增加 AgentSession 状态更新参数（注意：AgentSession update 必须在 `async with session.begin():` 块内执行，`session` 变量在该块内有效）：

```python
async def _save_response(
    *,
    # ... 现有参数（含 new_title return 改动）...
    agent_session_id: uuid.UUID | None = None,
    session_status: str = "completed",
) -> str | None:
    # ...
    async with AsyncSessionLocal() as session:
        async with session.begin():
            session.add(Message(...))  # 现有 Message insert
            if new_title:
                await session.execute(update(Conversation)...)  # 现有标题更新

            # AgentSession update 在同一事务内
            if agent_session_id:
                from datetime import datetime, timezone
                from sqlalchemy import update as sa_update

                await session.execute(
                    sa_update(AgentSession)
                    .where(AgentSession.id == agent_session_id)
                    .values(status=session_status, completed_at=datetime.now(timezone.utc))
                )
    # ...
    return new_title
```

在 `generate()` 的 except 块中，在调用 `_save_response` 之前，单独更新 AgentSession 为 error 状态：

```python
except Exception:
    logger.exception("chat_stream_error", conv_id=str(conv_id))
    if agent_session_id:
        try:
            async with AsyncSessionLocal() as _err_session:
                async with _err_session.begin():
                    from datetime import datetime, timezone
                    from sqlalchemy import update as sa_update

                    await _err_session.execute(
                        sa_update(AgentSession)
                        .where(AgentSession.id == agent_session_id)
                        .values(status="error", completed_at=datetime.now(timezone.utc))
                    )
        except Exception:
            logger.warning("agent_session_error_update_failed", exc_info=True)
    raise
```

**Step 3: 运行测试**

```bash
cd backend && uv run pytest tests/api/test_chat.py -v
cd backend && uv run ruff check --fix app/ && uv run ruff format app/
cd backend && uv run mypy app/
```

**Step 4: Commit**

```bash
git add backend/app/api/chat.py backend/tests/api/test_chat.py
git commit -m "feat(chat): write AgentSession lifecycle status to database"
```

---

### Task C-5：PR-C 验证 & Push

**Step 1: 完整验证**

```bash
cd backend && uv run pytest tests/ -v
cd backend && uv run mypy app
cd frontend && bun run lint:fix && bun run type-check
docker compose up -d && docker compose ps
pre-commit run --all-files
```

**Step 2: Push**

```bash
git push -u origin feature/ux-improvements
```

---

## 合并顺序

1. PR-B (`feature/perf-routing`) — 独立，先合并
2. PR-A (`fix/internal-cleanup`) — 从合并 PR-B 后的 `dev` 创建（因 PR-B Task B-2 和 PR-A Task A-2 都修改 `chat.py`）
3. PR-C (`feature/ux-improvements`) — 从合并 PR-A 后的 `dev` 创建
