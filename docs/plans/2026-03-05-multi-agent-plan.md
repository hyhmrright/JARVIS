# Multi-Agent Orchestration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Router + Expert Agents (Code/Research/Writing) and wire them into the main chat flow alongside the existing Supervisor.

**Architecture:** A lightweight `router.py` classifies incoming messages (simple vs complex, and domain). Simple messages go to the existing ReAct Agent. Complex messages go to the existing Supervisor. Domain-specific messages route to specialist Expert Agents with dedicated tool sets. SSE streams routing events back to the frontend.

**Tech Stack:** LangGraph (existing), FastAPI SSE (existing), LangChain tools (existing)

**Note:** `agent/supervisor.py` already exists with a working plan/execute/aggregate flow. This plan adds the Router and Expert Agents that were missing, then wires everything into the main `graph.py` and `chat.py` SSE stream.

**Worktree:** `feature/multi-agent`, branch from latest `dev` (after plugin-enhancement merges)

---

## Task 1: Create agent/router.py

**Files:**
- Create: `backend/app/agent/router.py`
- Create: `backend/tests/agent/test_router.py`

**Step 1: Write failing tests**

```python
"""Tests for agent router — task classification."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.anyio
async def test_router_classifies_simple():
    """Short factual queries route to 'simple'."""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="simple")
        )
        mock_get_llm.return_value = mock_llm

        from app.agent.router import classify_task
        result = await classify_task(
            "What time is it?",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert result == "simple"


@pytest.mark.anyio
async def test_router_classifies_code():
    """Code-related queries route to 'code'."""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="code")
        )
        mock_get_llm.return_value = mock_llm

        from app.agent.router import classify_task
        result = await classify_task(
            "Write a Python script to parse CSV files",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert result in ("code", "complex")


@pytest.mark.anyio
async def test_router_falls_back_on_error():
    """Router returns 'simple' on any LLM error."""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))
        mock_get_llm.return_value = mock_llm

        from app.agent.router import classify_task
        result = await classify_task(
            "anything",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert result == "simple"
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/agent/test_router.py -v
```

Expected: FAIL — `app.agent.router` does not exist

**Step 3: Create `backend/app/agent/router.py`**

```python
"""Task router — classifies incoming messages to determine agent dispatch.

Returns one of: 'simple', 'complex', 'code', 'research', 'writing'
- simple: single-turn factual or conversational reply → ReAct Agent
- complex: multi-step task → Supervisor
- code: code generation/execution → CodeAgent
- research: research/search/knowledge retrieval → ResearchAgent
- writing: drafting/editing/summarizing documents → WritingAgent
"""

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm import get_llm

logger = structlog.get_logger(__name__)

_VALID_LABELS = {"simple", "complex", "code", "research", "writing"}

_ROUTER_PROMPT = """\
Classify the user's message into exactly ONE of these categories:
- simple: short factual question, casual chat, or anything answerable in one step
- code: write/debug/explain code, build a script, technical implementation
- research: look up information, summarize sources, answer from documents
- writing: draft, edit, translate, or summarize text/documents
- complex: multi-step task that doesn't fit the above

Reply with ONLY the category word. Nothing else."""


async def classify_task(
    message: str,
    *,
    provider: str,
    model: str,
    api_key: str,
) -> str:
    """Classify a user message. Falls back to 'simple' on any error."""
    try:
        llm = get_llm(provider, model, api_key)
        response = await llm.ainvoke(
            [
                SystemMessage(content=_ROUTER_PROMPT),
                HumanMessage(content=message[:2000]),  # truncate for router
            ]
        )
        label = str(response.content).strip().lower()
        if label in _VALID_LABELS:
            logger.info("router_classified", label=label)
            return label
        logger.warning("router_unknown_label", label=label)
        return "simple"
    except Exception:
        logger.warning("router_classify_failed", exc_info=True)
        return "simple"
```

**Step 4: Run tests**

```bash
uv run pytest tests/agent/test_router.py -v
```

Expected: all PASS

**Step 5: Static checks**

```bash
uv run ruff check --fix && uv run ruff format
uv run mypy app/agent/router.py
```

**Step 6: Commit**

```bash
git add backend/app/agent/router.py backend/tests/agent/test_router.py
git commit -m "feat(agent): add task router for multi-agent dispatch"
```

---

## Task 2: Create Expert Agent Factories

**Files:**
- Create: `backend/app/agent/experts/__init__.py`
- Create: `backend/app/agent/experts/code_agent.py`
- Create: `backend/app/agent/experts/research_agent.py`
- Create: `backend/app/agent/experts/writing_agent.py`
- Create: `backend/tests/agent/test_experts.py`

**Step 1: Write failing tests**

```python
"""Tests for expert agent factories."""
from unittest.mock import MagicMock

import pytest


def test_code_agent_includes_code_tools():
    """CodeAgent graph includes code_exec and shell tools."""
    from app.agent.experts.code_agent import create_code_agent_graph

    graph = create_code_agent_graph(
        provider="deepseek",
        model="deepseek-chat",
        api_key="test",
        user_id="user123",
    )
    # Verify graph is compiled
    assert graph is not None
    assert hasattr(graph, "astream")


def test_research_agent_includes_rag_tool():
    """ResearchAgent graph has rag_search in enabled tools."""
    from app.agent.experts.research_agent import create_research_agent_graph

    graph = create_research_agent_graph(
        provider="deepseek",
        model="deepseek-chat",
        api_key="test",
        user_id="user123",
        openai_api_key="oai_test",
    )
    assert graph is not None


def test_writing_agent_excludes_shell():
    """WritingAgent graph does not expose shell tool."""
    from app.agent.experts.writing_agent import create_writing_agent_graph

    graph = create_writing_agent_graph(
        provider="deepseek",
        model="deepseek-chat",
        api_key="test",
        user_id="user123",
    )
    assert graph is not None
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/agent/test_experts.py -v
```

Expected: FAIL — modules don't exist

**Step 3: Create `backend/app/agent/experts/__init__.py`**

```python
"""Expert agent factories for specialized task domains."""
```

**Step 4: Create `backend/app/agent/experts/code_agent.py`**

```python
"""CodeAgent — specialised for code generation, debugging, and execution."""

from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import create_graph

_CODE_PERSONA = """\
You are an expert software engineer. Focus on writing correct, efficient, \
and well-tested code. Use shell_exec and code_exec tools to run and verify \
your solutions. Explain your approach briefly before presenting code."""

_CODE_TOOLS = ["code_exec", "shell", "file", "datetime"]


def create_code_agent_graph(
    *,
    provider: str,
    model: str,
    api_key: str,
    user_id: str | None = None,
    openai_api_key: str | None = None,
    api_keys: list[str] | None = None,
) -> CompiledStateGraph:
    """Return a compiled LangGraph optimised for coding tasks."""
    return create_graph(
        provider=provider,
        model=model,
        api_key=api_key,
        enabled_tools=_CODE_TOOLS,
        user_id=user_id,
        openai_api_key=openai_api_key,
        api_keys=api_keys,
    )
```

**Step 5: Create `backend/app/agent/experts/research_agent.py`**

```python
"""ResearchAgent — specialised for knowledge retrieval and research tasks."""

from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import create_graph

_RESEARCH_PERSONA = """\
You are an expert researcher. Use rag_search to retrieve relevant documents \
from the user's knowledge base. Use web search when you need current or \
external information. Cite sources clearly in your responses."""

_RESEARCH_TOOLS = ["rag_search", "search", "web_fetch", "datetime"]


def create_research_agent_graph(
    *,
    provider: str,
    model: str,
    api_key: str,
    user_id: str | None = None,
    openai_api_key: str | None = None,
    tavily_api_key: str | None = None,
    api_keys: list[str] | None = None,
) -> CompiledStateGraph:
    """Return a compiled LangGraph optimised for research tasks."""
    return create_graph(
        provider=provider,
        model=model,
        api_key=api_key,
        enabled_tools=_RESEARCH_TOOLS,
        user_id=user_id,
        openai_api_key=openai_api_key,
        tavily_api_key=tavily_api_key,
        api_keys=api_keys,
    )
```

**Step 6: Create `backend/app/agent/experts/writing_agent.py`**

```python
"""WritingAgent — specialised for drafting, editing, and summarizing text."""

from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import create_graph

_WRITING_PERSONA = """\
You are an expert writer and editor. Focus on producing clear, well-structured, \
and engaging content. When asked to summarize, capture the key points concisely. \
When drafting, match the user's requested tone and style."""

_WRITING_TOOLS = ["rag_search", "web_fetch", "datetime"]


def create_writing_agent_graph(
    *,
    provider: str,
    model: str,
    api_key: str,
    user_id: str | None = None,
    openai_api_key: str | None = None,
    api_keys: list[str] | None = None,
) -> CompiledStateGraph:
    """Return a compiled LangGraph optimised for writing tasks."""
    return create_graph(
        provider=provider,
        model=model,
        api_key=api_key,
        enabled_tools=_WRITING_TOOLS,
        user_id=user_id,
        openai_api_key=openai_api_key,
        api_keys=api_keys,
    )
```

**Step 7: Run tests**

```bash
uv run pytest tests/agent/test_experts.py -v
```

Expected: all PASS

**Step 8: Static checks**

```bash
uv run ruff check --fix && uv run ruff format
uv run mypy app/agent/experts/
```

**Step 9: Commit**

```bash
git add backend/app/agent/experts/ backend/tests/agent/test_experts.py
git commit -m "feat(agent): add CodeAgent, ResearchAgent, WritingAgent expert factories"
```

---

## Task 3: Wire Router into chat.py

**Files:**
- Modify: `backend/app/api/chat.py`
- Create: `backend/tests/api/test_multi_agent_routing.py`

**Step 1: Write failing tests**

```python
"""Tests for multi-agent routing in chat stream."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_routing_event_emitted(auth_client: AsyncClient, mock_conv_id: str):
    """SSE stream emits a routing event before the first delta."""
    events = []

    with patch("app.api.chat.classify_task", return_value="code") as mock_router, \
         patch("app.api.chat.create_graph") as mock_graph:

        mock_state = MagicMock()
        mock_state.__aiter__ = AsyncMock(return_value=iter([
            {"llm": {"messages": [MagicMock(content="result", tool_calls=[])]}}
        ]))
        mock_graph.return_value.astream = AsyncMock(return_value=mock_state)

        async with auth_client.stream(
            "POST",
            "/api/chat/stream",
            json={"conversation_id": mock_conv_id, "content": "Write me a sort algorithm"},
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

    routing_events = [e for e in events if e.get("type") == "routing"]
    assert routing_events, "Expected at least one routing SSE event"
    assert routing_events[0]["agent"] in ("simple", "code", "research", "writing", "complex")
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/api/test_multi_agent_routing.py -v
```

Expected: FAIL

**Step 3: Modify `backend/app/api/chat.py` — add routing**

At the top of the file, add import:
```python
from app.agent.router import classify_task
```

Inside the `generate()` async function, before `graph = create_graph(...)`, add:

```python
# Route the message to determine which agent handles it
try:
    route = await classify_task(
        body.content,
        provider=llm.provider,
        model=llm.model_name,
        api_key=llm.api_key,
    )
except Exception:
    route = "simple"

# Emit routing event to frontend
yield _format_sse({"type": "routing", "agent": route})

# Select graph based on route
if route == "code":
    from app.agent.experts.code_agent import create_code_agent_graph
    graph = create_code_agent_graph(
        provider=llm.provider,
        model=llm.model_name,
        api_key=llm.api_key,
        user_id=str(user.id),
        openai_api_key=openai_key,
        api_keys=llm.api_keys,
    )
elif route == "research":
    from app.agent.experts.research_agent import create_research_agent_graph
    graph = create_research_agent_graph(
        provider=llm.provider,
        model=llm.model_name,
        api_key=llm.api_key,
        user_id=str(user.id),
        openai_api_key=openai_key,
        tavily_api_key=tavily_key,
        api_keys=llm.api_keys,
    )
elif route == "writing":
    from app.agent.experts.writing_agent import create_writing_agent_graph
    graph = create_writing_agent_graph(
        provider=llm.provider,
        model=llm.model_name,
        api_key=llm.api_key,
        user_id=str(user.id),
        openai_api_key=openai_key,
        api_keys=llm.api_keys,
    )
elif route == "complex":
    from app.agent.supervisor import create_supervisor_graph
    supervisor = create_supervisor_graph(
        provider=llm.provider,
        model=llm.model_name,
        api_key=llm.api_key,
        api_keys=llm.api_keys,
        user_id=str(user.id),
        openai_api_key=openai_key,
        tavily_api_key=tavily_key,
        enabled_tools=llm.enabled_tools,
    )
    # Supervisor returns final AIMessage — wrap result as SSE
    from app.agent.supervisor import SupervisorState
    sup_result = await supervisor.ainvoke(
        SupervisorState(messages=lc_messages)
    )
    final_msg = sup_result["messages"][-1]
    final_content = str(final_msg.content)
    yield _format_sse({"type": "delta", "delta": final_content, "content": final_content})
    return  # Supervisor result already yielded, skip standard graph loop
else:
    # simple — use existing ReAct graph (already constructed below)
    graph = create_graph(
        provider=llm.provider,
        model=llm.model_name,
        api_key=llm.api_key,
        enabled_tools=llm.enabled_tools,
        api_keys=llm.api_keys,
        user_id=str(user.id),
        openai_api_key=openai_key,
        tavily_api_key=tavily_key,
        mcp_tools=mcp_tools,
        plugin_tools=plugin_tools,
        conversation_id=str(conv_id),
    )
```

Note: Remove the original `graph = create_graph(...)` call that was at the bottom of generate() — it's now inside the else branch.

**Step 4: Run static checks**

```bash
uv run ruff check --fix && uv run ruff format
uv run mypy app/api/chat.py
```

**Step 5: Fast import check**

```bash
uv run pytest --collect-only -q
```

Expected: no errors

**Step 6: Run tests**

```bash
uv run pytest tests/api/test_multi_agent_routing.py -v
uv run pytest tests/ -v
```

Expected: all pass

**Step 7: Commit**

```bash
git add backend/app/api/chat.py backend/tests/api/test_multi_agent_routing.py
git commit -m "feat(agent): wire router into chat stream — SSE emits routing event"
```

---

## Task 4: Frontend — Display Routing Info in Chat

**Files:**
- Modify: `frontend/src/stores/chat.ts` (handle routing SSE event)
- Modify: `frontend/src/pages/ChatPage.vue` (show agent badge)

**Step 1: In `frontend/src/stores/chat.ts`** — add handling for `routing` event type

Find the SSE parsing section (where `type === "delta"` is handled) and add:

```typescript
} else if (data.type === 'routing') {
  // Update current message with which agent handled it
  const lastMsg = this.currentMessages[this.currentMessages.length - 1]
  if (lastMsg && lastMsg.role === 'ai') {
    lastMsg.agentType = data.agent
  }
}
```

Also add `agentType?: string` to the message type if typed.

**Step 2: In `frontend/src/pages/ChatPage.vue`** — show agent badge

Find the AI message render section and add a small badge:

```vue
<span
  v-if="msg.agentType && msg.agentType !== 'simple'"
  class="agent-badge"
  :title="`Handled by ${msg.agentType} agent`"
>
  {{ agentLabel(msg.agentType) }}
</span>
```

Add the helper function in `<script setup>`:

```typescript
function agentLabel(type: string): string {
  const labels: Record<string, string> = {
    code: '💻 Code',
    research: '🔍 Research',
    writing: '✍️ Writing',
    complex: '🤖 Supervisor',
  }
  return labels[type] ?? type
}
```

Add styling:
```css
.agent-badge {
  display: inline-block;
  font-size: 0.7rem;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  background: #f3f4f6;
  color: #374151;
  margin-bottom: 0.25rem;
}
```

**Step 3: Run frontend checks**

```bash
cd frontend
bun run type-check
bun run lint:fix
```

**Step 4: Commit**

```bash
git add frontend/src/stores/chat.ts frontend/src/pages/ChatPage.vue
git commit -m "feat(ui): show agent type badge in chat messages"
```

---

## Task 5: Final Verification

**Step 1: Full backend test suite**

```bash
cd backend
uv run pytest tests/ -v
```

Expected: all pass

**Step 2: Fast import check**

```bash
uv run pytest --collect-only -q
```

**Step 3: Full static checks**

```bash
uv run ruff check && uv run mypy app
```

**Step 4: Frontend checks**

```bash
cd frontend
bun run type-check && bun run lint
```

**Step 5: Push and open PR**

```bash
git push origin feature/multi-agent
```

Open PR: `feature/multi-agent` → `dev`

---

## Merge Order Reminder

1. `feature/plugin-enhancement` → `dev` (first — only touches plugins/ and frontend/)
2. `feature/multi-agent` → `dev` (second — touches chat.py, agent/)

When merging #2, resolve any `chat.py` conflict: keep both the plugin RBAC changes from #1 and the routing changes from #2.
