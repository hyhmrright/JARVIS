# P1: Core Agent Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `chat_stream()` from 472 lines to ≤50 lines, consolidate three duplicated agent execution paths into one `AgentExecutionService`, and simplify `create_graph()` from 18 parameters to 1.

**Architecture:** (1) Introduce `AgentConfig` dataclass in `app/core/llm_config.py` that bundles all graph-construction parameters. (2) Refactor `create_graph()` and `build_expert_graph()` to accept `AgentConfig`. (3) Extract `build_chat_context()` into `app/api/chat/context.py`. (4) Extract the streaming generator into a module-level function. (5) Add `AgentExecutionService.run_blocking()` and delegate `run_agent_for_user()` to it. Prerequisite: P2 must be merged first (for `AgentGraphFactory` and `MemoryRepository`).

**Tech Stack:** Python dataclasses, LangGraph `CompiledStateGraph`, FastAPI `StreamingResponse`, SQLAlchemy async

---

### Task 1: Move `ResolvedLLMConfig` to `app/core/llm_config.py` and add `AgentConfig`

**Files:**
- Create: `backend/app/core/llm_config.py`
- Modify: `backend/app/api/deps.py` (re-export for backward compat)
- Test: `backend/tests/core/test_llm_config.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/core/test_llm_config.py
import pytest
from app.core.llm_config import AgentConfig, ResolvedLLMConfig


def _make_llm() -> ResolvedLLMConfig:
    return ResolvedLLMConfig(
        provider="deepseek",
        model_name="deepseek-chat",
        api_key="sk-test",
        api_keys=["sk-test"],
        enabled_tools=None,
        persona_override=None,
        raw_keys={},
    )


def test_agent_config_defaults():
    llm = _make_llm()
    cfg = AgentConfig(llm=llm)
    assert cfg.user_id is None
    assert cfg.conversation_id is None
    assert cfg.depth == 0
    assert cfg.mcp_tools == []
    assert cfg.plugin_tools == []
    assert cfg.openai_api_key is None
    assert cfg.tavily_api_key is None


def test_agent_config_full():
    llm = _make_llm()
    cfg = AgentConfig(
        llm=llm,
        user_id="u1",
        conversation_id="c1",
        depth=1,
        openai_api_key="sk-openai",
        tavily_api_key="tv-key",
    )
    assert cfg.user_id == "u1"
    assert cfg.depth == 1


def test_resolved_llm_config_re_exported_from_deps():
    """Existing callers that import from app.api.deps must still work."""
    from app.api.deps import ResolvedLLMConfig as DepsCopy
    assert DepsCopy is ResolvedLLMConfig
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/core/test_llm_config.py -v
```
Expected: `ImportError` — module doesn't exist.

- [ ] **Step 3: Create `app/core/llm_config.py`**

```python
# backend/app/core/llm_config.py
"""LLM configuration dataclasses shared between the API and agent layers.

``ResolvedLLMConfig`` was previously defined in ``app/api/deps.py``.  It is
moved here so that the agent layer (``app/agent/``) and services layer
(``app/services/``) can import it without creating an upward dependency on the
API layer.

``app/api/deps.py`` re-exports ``ResolvedLLMConfig`` for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ResolvedLLMConfig:
    """Immutable container for resolved LLM provider settings.

    Produced by ``app/api/deps.py::get_llm_config()`` after decrypting
    user API keys and resolving workspace overrides.
    """

    provider: str
    model_name: str
    api_key: str
    api_keys: list[str]
    enabled_tools: list[str] | None
    persona_override: str | None
    raw_keys: dict[str, Any]
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    system_prompt: str | None = None


@dataclass
class AgentConfig:
    """All parameters needed to compile and run a LangGraph agent.

    Replaces the 18-parameter ``create_graph()`` signature.  Callers
    build one ``AgentConfig``, pass it to ``create_graph(config)`` or
    ``AgentExecutionService``, and are insulated from future parameter additions.

    ``llm`` is required; all other fields are optional with safe defaults.
    """

    llm: ResolvedLLMConfig

    # Runtime context
    user_id: str | None = None
    conversation_id: str | None = None
    depth: int = 0

    # Tool overrides
    mcp_tools: list = field(default_factory=list)   # list[BaseTool]
    plugin_tools: list = field(default_factory=list)  # list[BaseTool]

    # Third-party keys needed by specific tools
    openai_api_key: str | None = None   # RAG search + image generation
    tavily_api_key: str | None = None   # web search
```

- [ ] **Step 4: Update `app/api/deps.py` to re-export `ResolvedLLMConfig`**

In `app/api/deps.py`, find the `@dataclass` definition of `ResolvedLLMConfig` (lines 28–41) and replace it with an import + re-export:

```python
# In app/api/deps.py — replace the ResolvedLLMConfig @dataclass definition with:
from app.core.llm_config import AgentConfig as AgentConfig  # noqa: F401 re-export
from app.core.llm_config import ResolvedLLMConfig as ResolvedLLMConfig  # noqa: F401 re-export
```

Keep everything else in `deps.py` unchanged.

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/core/test_llm_config.py -v
```
Expected: all 3 tests `PASSED`.

- [ ] **Step 6: Run import check — no regressions**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```
Expected: collection succeeds.

- [ ] **Step 7: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
git add app/core/llm_config.py app/api/deps.py tests/core/test_llm_config.py
git commit -m "refactor: move ResolvedLLMConfig to app/core/llm_config, add AgentConfig"
```

---

### Task 2: Refactor `app/agent/graph.py` — `create_graph(config: AgentConfig)`

**Files:**
- Modify: `backend/app/agent/graph.py`
- Modify: `backend/tests/agent/test_compiler.py` (update mock targets if needed)

- [ ] **Step 1: Add `AgentConfig`-accepting overload to `create_graph()`**

Strategy: add a new `create_graph(config: AgentConfig)` signature while keeping the old signature working temporarily. This is done by checking the first argument type.

Replace the current `create_graph` signature:

```python
# backend/app/agent/graph.py — new create_graph signature

from app.core.llm_config import AgentConfig, ResolvedLLMConfig  # add import at top


def create_graph(  # noqa: C901
    config_or_provider: AgentConfig | str,
    model: str | None = None,
    api_key: str | None = None,
    enabled_tools: list[str] | None = None,
    *,
    api_keys: list[str] | None = None,
    user_id: str | None = None,
    openai_api_key: str | None = None,
    tavily_api_key: str | None = None,
    depth: int = 0,
    mcp_tools: list[BaseTool] | None = None,
    plugin_tools: list[BaseTool] | None = None,
    conversation_id: str | None = None,
    fallback_providers: list[dict] | None = None,
    base_url: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> CompiledStateGraph:
    """Compile a LangGraph ReAct agent.

    Preferred call signature (new):
        create_graph(config: AgentConfig) -> CompiledStateGraph

    Legacy positional signature (deprecated, still supported):
        create_graph(provider, model, api_key, ...) -> CompiledStateGraph
    """
    # Normalise: accept either AgentConfig or the old flat parameters
    if isinstance(config_or_provider, AgentConfig):
        config = config_or_provider
        provider = config.llm.provider
        model = config.llm.model_name
        api_key = config.llm.api_key
        api_keys = config.llm.api_keys
        enabled_tools = config.llm.enabled_tools
        user_id = config.user_id
        openai_api_key = config.openai_api_key
        tavily_api_key = config.tavily_api_key
        depth = config.depth
        mcp_tools = config.mcp_tools or None
        plugin_tools = config.plugin_tools or None
        conversation_id = config.conversation_id
        base_url = config.llm.base_url
        temperature = config.llm.temperature
        max_tokens = config.llm.max_tokens
    else:
        # Legacy flat-arg path — all callers will be migrated in Task 5/6/7
        provider = config_or_provider  # type: ignore[assignment]

    # ... rest of function body unchanged ...
```

The rest of the function body (tool resolution, graph compilation) is unchanged.

- [ ] **Step 2: Run existing agent tests**

```bash
cd backend && uv run pytest tests/agent/ -v --tb=short
```
Expected: all existing tests still `PASSED` (backward-compat path works).

- [ ] **Step 3: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/agent/graph.py
git commit -m "refactor: create_graph() accepts AgentConfig (backward-compat legacy path kept)"
```

---

### Task 3: Refactor `app/api/chat/graph_builder.py` — `build_expert_graph(config: AgentConfig)`

**Files:**
- Modify: `backend/app/api/chat/graph_builder.py`

- [ ] **Step 1: Rewrite `build_expert_graph()` to accept `AgentConfig`**

Current signature has 16 parameters. New signature: `build_expert_graph(route: str, config: AgentConfig) -> CompiledStateGraph`.

```python
# backend/app/api/chat/graph_builder.py — updated build_expert_graph

from app.core.llm_config import AgentConfig  # add to imports


def build_expert_graph(
    route: str,
    config: AgentConfig,
) -> CompiledStateGraph:
    """Return the appropriate compiled LangGraph for the given routing label.

    Expert agents (code/research/writing) select a focused tool subset.
    Workflow DSLs take precedence over default agents.
    Unknown labels fall back to the standard ReAct graph.
    """
    if config.workflow_dsl:  # AgentConfig.workflow_dsl set in Task 1
        from app.agent.compiler import GraphCompiler, WorkflowDSL
        compiler = GraphCompiler(
            dsl=WorkflowDSL(**config.workflow_dsl),
            llm_config={
                "provider": config.llm.provider,
                "api_key": config.llm.api_key,
                "base_url": config.llm.base_url,
                "temperature": config.llm.temperature,
                **({"max_tokens": config.llm.max_tokens} if config.llm.max_tokens else {}),
            },
        )
        return compiler.compile()

    from app.agent.experts import (
        create_code_expert_graph,
        create_research_expert_graph,
        create_writing_expert_graph,
    )

    expert_builders = {
        "code": create_code_expert_graph,
        "research": create_research_expert_graph,
        "writing": create_writing_expert_graph,
    }

    if builder := expert_builders.get(route):
        return builder(config)
    return create_graph(config)
```

Note: `_workflow_dsl` is a temporary attribute set by `build_chat_context()` (Task 4) on the config when a conversation has a workflow DSL stored. This avoids adding `workflow_dsl` to the core `AgentConfig` dataclass (YAGNI — workflow DSL is a chat-layer concern).

Actually, keep it simpler: add `workflow_dsl: dict | None = None` to `AgentConfig` in `llm_config.py` since it's used in both chat and gateway paths.

Update `AgentConfig` in `app/core/llm_config.py`:
```python
@dataclass
class AgentConfig:
    llm: ResolvedLLMConfig
    user_id: str | None = None
    conversation_id: str | None = None
    depth: int = 0
    mcp_tools: list = field(default_factory=list)
    plugin_tools: list = field(default_factory=list)
    openai_api_key: str | None = None
    tavily_api_key: str | None = None
    workflow_dsl: dict | None = None  # ← add this field
```

- [ ] **Step 2: Run import check**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```
Expected: collection succeeds.

- [ ] **Step 3: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/api/chat/graph_builder.py app/core/llm_config.py
git commit -m "refactor: build_expert_graph() accepts AgentConfig"
```

---

### Task 4: Create `app/api/chat/context.py` — `build_chat_context()`

**Files:**
- Create: `backend/app/api/chat/context.py`
- Test: `backend/tests/api/test_chat_context.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/test_chat_context.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from langchain_core.messages import HumanMessage, SystemMessage

from app.api.chat.context import build_chat_context
from app.api.deps import ResolvedLLMConfig
from app.api.chat.schemas import ChatRequest


def _make_llm(tools=None):
    return ResolvedLLMConfig(
        provider="deepseek",
        model_name="deepseek-chat",
        api_key="sk-test",
        api_keys=["sk-test"],
        enabled_tools=tools,
        persona_override=None,
        raw_keys={},
        system_prompt=None,
    )


def _make_request(conv_id=None, content="hello"):
    conv_id = conv_id or uuid.uuid4()
    return ChatRequest(
        conversation_id=conv_id,
        content=content,
        parent_message_id=None,
        workspace_id=None,
    )


@pytest.mark.anyio
async def test_build_chat_context_returns_lc_messages(fake_db):
    """build_chat_context() must return a non-empty list of LangChain messages."""
    conv_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Minimal stubs
    mock_conv = MagicMock()
    mock_conv.id = conv_id
    mock_conv.persona_id = None
    mock_conv.persona_override = None
    mock_conv.workflow_dsl = None
    mock_conv.active_leaf_id = None

    fake_db.scalar = AsyncMock(return_value=mock_conv)
    fake_db.scalars = AsyncMock(return_value=MagicMock(all=lambda: []))
    fake_db.commit = AsyncMock()

    user = MagicMock()
    user.id = user_id

    llm = _make_llm()
    request = _make_request(conv_id)

    with patch("app.api.chat.context.build_rag_context", AsyncMock(return_value=None)):
        with patch("app.api.chat.context.build_memory_message", AsyncMock(return_value=None)):
            ctx = await build_chat_context(request, user, fake_db, llm)

    assert ctx.lc_messages  # non-empty
    assert any(isinstance(m, SystemMessage) for m in ctx.lc_messages)
    assert ctx.conv_id == conv_id
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/api/test_chat_context.py -v
```
Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Create `app/api/chat/context.py`**

This module contains all the setup logic currently in `chat_stream()` lines 56–220.

```python
# backend/app/api/chat/context.py
"""Chat context builder — extracted from the monolithic chat_stream() handler.

``build_chat_context()`` encapsulates everything needed before invoking the
agent:  conversation lookup, persona resolution, message history, RAG
injection, and memory injection.  The result is a ``ChatContext`` that
``chat_stream()`` passes directly to the streaming generator.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.persona import build_system_prompt
from app.api.chat.message_builder import (
    build_langchain_messages,
    build_memory_message,
    walk_message_chain,
)
from app.api.chat.schemas import ChatRequest
from app.api.deps import ResolvedLLMConfig
from app.core.sanitizer import sanitize_user_input
from app.core.security import resolve_api_key
from app.db.models import Conversation, Message, User
from app.rag.context import build_rag_context


@dataclass
class ChatContext:
    """Everything the streaming generator needs, resolved before streaming starts."""

    lc_messages: list[BaseMessage]
    conv_id: uuid.UUID
    human_msg_id: uuid.UUID | None
    user_content: str
    is_consent: bool
    approved: bool | None
    is_first_exchange: bool
    parent_message_id: uuid.UUID | None
    workflow_dsl: dict | None = None
    openai_key: str | None = None


async def build_chat_context(
    body: ChatRequest,
    user: User,
    db: AsyncSession,
    llm: ResolvedLLMConfig,
) -> ChatContext:
    """Resolve conversation, history, persona, RAG, and memory into a ChatContext.

    Raises ``HTTPException(404)`` if the conversation does not exist or does
    not belong to the current user.
    """
    from dataclasses import replace as dc_replace
    from fastapi import HTTPException
    from app.api.settings import PROVIDER_MODELS

    # --- model override ---
    if body.model_override:
        allowed = PROVIDER_MODELS.get(llm.provider, [])
        if allowed and body.model_override not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"model '{body.model_override}' not valid for '{llm.provider}'",
            )
        llm = dc_replace(llm, model_name=body.model_override)

    user_content = sanitize_user_input(body.content)
    is_consent = user_content.startswith("[CONSENT:")
    approved: bool | None = None
    if is_consent:
        approved = "ALLOW" in user_content

    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404)

    # --- persona resolution ---
    if not is_consent:
        from app.db.models import Persona
        from dataclasses import replace as dc_replace  # noqa: F811

        if conv.persona_id:
            _persona = await db.scalar(
                select(Persona).where(Persona.id == conv.persona_id)
            )
            if _persona:
                if not conv.persona_override:
                    conv.persona_override = _persona.system_prompt
                    await db.commit()
                if _persona.model_name:
                    llm = dc_replace(llm, model_name=_persona.model_name)
                if _persona.temperature is not None:
                    llm = dc_replace(llm, temperature=_persona.temperature)
                if _persona.enabled_tools is not None:
                    llm = dc_replace(llm, enabled_tools=_persona.enabled_tools)
        elif body.persona_id or body.workflow_dsl:
            _msg_count = await db.scalar(
                select(func.count(Message.id)).where(
                    Message.conversation_id == conv.id
                )
            )
            if (_msg_count or 0) == 0:
                if body.persona_id:
                    _persona = await db.scalar(
                        select(Persona).where(
                            Persona.id == body.persona_id,
                            Persona.user_id == user.id,
                        )
                    )
                    if _persona:
                        conv.persona_override = _persona.system_prompt
                        await db.commit()
                if body.workflow_dsl:
                    conv.workflow_dsl = body.workflow_dsl
                    await db.commit()
    elif body.workflow_dsl and not is_consent:
        _msg_count = await db.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == conv.id)
        )
        if (_msg_count or 0) == 0:
            conv.workflow_dsl = body.workflow_dsl
            await db.commit()

    parent_message_id = body.parent_message_id or conv.active_leaf_id

    # --- persist human message ---
    human_msg_id: uuid.UUID | None = None
    if not is_consent:
        final_content = user_content
        if body.file_context:
            final_content = (
                f"[Attached file: {body.file_context.filename}]\n"
                f"{body.file_context.extracted_text}\n\n----- \n{user_content}"
            )
        human_msg = Message(
            conversation_id=conv.id,
            role="human",
            content=final_content,
            image_urls=body.image_urls,
            parent_id=parent_message_id,
        )
        db.add(human_msg)
        await db.commit()
        await db.refresh(human_msg)
        human_msg_id = human_msg.id

    # --- build message history ---
    history_rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    all_conv_messages = history_rows.all()
    msg_dict = {msg.id: msg for msg in all_conv_messages}

    start_id = human_msg_id if not is_consent else parent_message_id
    if not start_id and all_conv_messages:
        start_id = all_conv_messages[-1].id

    all_history = walk_message_chain(msg_dict, start_id)
    lc_messages = build_langchain_messages(all_history)

    # --- system prompt ---
    if llm.system_prompt:
        system_msg = SystemMessage(content=llm.system_prompt)
    else:
        system_msg = SystemMessage(content=build_system_prompt(llm.persona_override))
    lc_messages = [system_msg, *lc_messages]

    # --- memory injection ---
    _mem_msg = await build_memory_message(db, user.id)
    if _mem_msg:
        lc_messages = [lc_messages[0], _mem_msg, *lc_messages[1:]]

    is_first_exchange = sum(1 for m in lc_messages if isinstance(m, AIMessage)) == 0

    # --- RAG injection ---
    openai_key = resolve_api_key("openai", llm.raw_keys)
    last_ai_content = next(
        (msg.content for msg in reversed(lc_messages) if isinstance(msg, AIMessage)),
        "",
    )
    rag_query = (
        f"{user_content}\n{last_ai_content[:200]}" if last_ai_content else user_content
    )
    workspace_ids = [str(body.workspace_id)] if body.workspace_id else None
    rag_ctx = await build_rag_context(
        str(user.id), rag_query, openai_key, workspace_ids=workspace_ids
    )
    if rag_ctx:
        lc_messages = [
            lc_messages[0],
            SystemMessage(content=rag_ctx),
            *lc_messages[1:],
        ]

    return ChatContext(
        lc_messages=lc_messages,
        conv_id=conv.id,
        human_msg_id=human_msg_id,
        user_content=user_content,
        is_consent=is_consent,
        approved=approved,
        is_first_exchange=is_first_exchange,
        parent_message_id=parent_message_id,
        workflow_dsl=conv.workflow_dsl,
        openai_key=openai_key,
    )
```

- [ ] **Step 4: Run test**

```bash
cd backend && uv run pytest tests/api/test_chat_context.py -v
```
Expected: `PASSED`.

- [ ] **Step 5: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/api/chat/context.py tests/api/test_chat_context.py
git commit -m "feat: extract build_chat_context() into app/api/chat/context.py"
```

---

### Task 5: Create `app/services/agent_execution.py` — `run_blocking()`

**Files:**
- Create: `backend/app/services/agent_execution.py`
- Test: `backend/tests/services/test_agent_execution.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/test_agent_execution.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.llm_config import AgentConfig, ResolvedLLMConfig
from app.services.agent_execution import AgentExecutionService


def _make_config(user_id=None):
    llm = ResolvedLLMConfig(
        provider="deepseek",
        model_name="deepseek-chat",
        api_key="sk-test",
        api_keys=["sk-test"],
        enabled_tools=[],
        persona_override=None,
        raw_keys={},
    )
    return AgentConfig(llm=llm, user_id=user_id or str(uuid.uuid4()))


@pytest.mark.anyio
async def test_run_blocking_returns_ai_reply():
    """run_blocking() must return the last AI message content as a string."""
    from langchain_core.messages import AIMessage, HumanMessage

    config = _make_config()
    messages = [HumanMessage(content="hello")]

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"messages": [AIMessage(content="Hi there!")]}
    )

    with patch(
        "app.services.agent_execution.create_graph",
        return_value=mock_graph,
    ):
        svc = AgentExecutionService()
        result = await svc.run_blocking(messages, config)

    assert result == "Hi there!"


@pytest.mark.anyio
async def test_run_blocking_raises_on_empty_messages():
    """run_blocking() must raise ValueError when graph returns no messages."""
    from langchain_core.messages import HumanMessage

    config = _make_config()
    messages = [HumanMessage(content="hello")]

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value={"messages": []})

    with patch("app.services.agent_execution.create_graph", return_value=mock_graph):
        svc = AgentExecutionService()
        with pytest.raises(ValueError, match="no messages"):
            await svc.run_blocking(messages, config)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/services/test_agent_execution.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Create `app/services/agent_execution.py`**

```python
# backend/app/services/agent_execution.py
"""Unified agent execution service.

Before this module, agent execution logic was duplicated in:
  - app/api/chat/routes.py::chat_stream()  (streaming path)
  - app/gateway/router.py::_run_agent()    (channel gateway path)
  - app/gateway/agent_runner.py::run_agent_for_user()  (cron/webhook path)

This service owns the *blocking* execution path.  The streaming path still
lives in routes.py because it is tightly coupled to SSE formatting,
per-chunk message persistence, and FastAPI's disconnect detection — all of
which are HTTP-layer concerns, not agent-layer concerns.
"""

from __future__ import annotations

import structlog
from langchain_core.messages import BaseMessage, ToolMessage

from app.agent.graph import create_graph
from app.agent.state import AgentState
from app.core.llm_config import AgentConfig

logger = structlog.get_logger(__name__)


class AgentExecutionService:
    """Run the JARVIS agent graph in blocking (non-streaming) mode.

    Used by background runners (cron jobs, webhooks, gateway channels) that
    need the final AI response as a string without SSE.
    """

    async def run_blocking(
        self,
        messages: list[BaseMessage],
        config: AgentConfig,
    ) -> str:
        """Invoke the agent graph and return the final AI message content.

        Raises:
            ValueError: if the graph returns no messages (should not happen
                        in normal operation but guards against broken graphs).
        """
        graph = create_graph(config)
        result = await graph.ainvoke(AgentState(messages=messages))

        result_messages = result.get("messages", [])
        if not result_messages:
            raise ValueError(
                f"Agent graph returned no messages for user_id={config.user_id}"
            )

        ai_content = str(result_messages[-1].content)

        tools_used = [
            m.name
            for m in result_messages
            if isinstance(m, ToolMessage) and m.name
        ]
        # Remove duplicates while preserving order
        seen: set[str] = set()
        tools_used = [t for t in tools_used if not (t in seen or seen.add(t))]  # type: ignore[func-returns-value]

        logger.info(
            "agent_execution_completed",
            user_id=config.user_id,
            reply_chars=len(ai_content),
            tools_used=tools_used,
        )
        return ai_content
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/services/test_agent_execution.py -v
```
Expected: both tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/services/agent_execution.py tests/services/test_agent_execution.py
git commit -m "feat: add AgentExecutionService with run_blocking() method"
```

---

### Task 6: Refactor `app/gateway/agent_runner.py` to use `AgentExecutionService`

**Files:**
- Modify: `backend/app/gateway/agent_runner.py`
- Modify: `backend/tests/gateway/test_agent_runner.py` (update mock targets)

- [ ] **Step 1: Rewrite `run_agent_for_user()` using the service**

The new version delegates the graph execution to `AgentExecutionService.run_blocking()`.
All user-settings loading, conversation creation, message building, and persistence stays in this function (those are infrastructure concerns, not agent concerns).

```python
# backend/app/gateway/agent_runner.py — new run_agent_for_user()

async def run_agent_for_user(
    user_id: str,
    task: str,
    trigger_ctx: dict | None = None,
) -> str:
    """Execute the JARVIS agent for a background task (cron / webhook).

    Creates a new conversation, runs the agent, persists the response,
    and returns the AI reply string.  Raises on failure.
    """
    from app.core.llm_config import AgentConfig, ResolvedLLMConfig
    from app.services.agent_execution import AgentExecutionService

    try:
        async with AsyncSessionLocal() as db:
            us = await db.scalar(
                select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id))
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
            if not api_keys:
                logger.warning("agent_runner_no_api_keys", user_id=user_id)
                return "未配置可用的 API Key，请先在设置页面中添加。"

            # Build conversation and messages (unchanged from original)
            conv = Conversation(
                user_id=uuid.UUID(user_id),
                title=f"Auto: {task[:60]}",
            )
            db.add(conv)
            await db.flush()

            ctx_block = format_trigger_context(trigger_ctx)
            full_task = f"{ctx_block}\n\n[用户任务]\n{task}" if ctx_block else task

            openai_key = resolve_api_key("openai", raw_keys)
            rag_context = await build_rag_context(user_id, full_task, openai_key)

            human_msg = Message(
                conversation_id=conv.id, role="human", content=full_task
            )
            db.add(human_msg)
            await db.flush()

            system_content = build_system_prompt(persona)
            lc_messages = [
                SystemMessage(content=system_content),
                *([SystemMessage(content=rag_context)] if rag_context else []),
                HumanMessage(content=full_task),
            ]

            mcp_tools: list = []
            if "mcp" in enabled:
                from app.tools.mcp_client import create_mcp_tools, parse_mcp_configs
                mcp_tools = await create_mcp_tools(
                    parse_mcp_configs(settings.mcp_servers_json)
                )

            # Build AgentConfig — replaces the 12-param create_graph() call
            llm = ResolvedLLMConfig(
                provider=provider,
                model_name=model_name,
                api_key=api_keys[0],
                api_keys=api_keys,
                enabled_tools=enabled,
                persona_override=persona,
                raw_keys=raw_keys,
                base_url=raw_keys.get(f"{provider}_base_url")
                if isinstance(raw_keys.get(f"{provider}_base_url"), str)
                else None,
            )
            config = AgentConfig(
                llm=llm,
                user_id=user_id,
                conversation_id=str(conv.id),
                mcp_tools=mcp_tools,
                openai_api_key=openai_key,
                tavily_api_key=settings.tavily_api_key,
            )

            # Create AgentSession
            agent_session_id: uuid.UUID | None = None
            try:
                ag = AgentSession(
                    conversation_id=conv.id,
                    agent_type="main",
                    status="active",
                )
                db.add(ag)
                await db.flush()
                agent_session_id = ag.id
            except Exception:
                logger.warning("agent_session_create_failed", exc_info=True)

            # Delegate to service — no more 12-param create_graph() call
            svc = AgentExecutionService()
            run_error = False
            try:
                ai_content = await svc.run_blocking(lc_messages, config)
            except Exception:
                run_error = True
                raise
            finally:
                if agent_session_id:
                    _update_agent_session(agent_session_id, run_error, model_name, provider)

            db.add(Message(
                conversation_id=conv.id,
                role="ai",
                content=ai_content,
                model_provider=provider,
                model_name=model_name,
            ))
            await db.commit()

            logger.info("agent_runner_completed", user_id=user_id, reply_chars=len(ai_content))
            return ai_content
    except Exception:
        logger.exception("agent_runner_error", user_id=user_id)
        raise
```

Extract `_update_agent_session()` as a small helper at module level:

```python
async def _update_agent_session(
    session_id: uuid.UUID,
    is_error: bool,
    model_name: str,
    provider: str,
) -> None:
    """Update AgentSession status in an isolated session."""
    from datetime import UTC, datetime
    from sqlalchemy import update
    try:
        async with AsyncSessionLocal() as sess:
            async with sess.begin():
                await sess.execute(
                    update(AgentSession)
                    .where(AgentSession.id == session_id)
                    .values(
                        status="error" if is_error else "completed",
                        completed_at=datetime.now(UTC),
                        metadata_json={"model": model_name, "provider": provider},
                    )
                )
    except Exception:
        logger.warning("agent_session_update_failed", exc_info=True)
```

- [ ] **Step 2: Update mock targets in `tests/gateway/test_agent_runner.py`**

Find the existing mock target for `create_graph`:
```python
# Before (old mock target):
patch("app.gateway.agent_runner.create_graph", ...)

# After (new mock target — patch the service method):
patch("app.services.agent_execution.AgentExecutionService.run_blocking", AsyncMock(return_value="mocked reply"))
```

- [ ] **Step 3: Run gateway tests**

```bash
cd backend && uv run pytest tests/gateway/ -v --tb=short
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add app/gateway/agent_runner.py tests/gateway/test_agent_runner.py
git commit -m "refactor: agent_runner uses AgentExecutionService.run_blocking()"
```

---

### Task 7: Simplify `app/api/chat/routes.py`

**Files:**
- Modify: `backend/app/api/chat/routes.py`
- Modify: `backend/tests/api/test_chat.py` (update mock targets)

- [ ] **Step 1: Extract `generate()` to module level + simplify `chat_stream()`**

The goal: `chat_stream()` becomes ≤50 lines. Move the inner `generate()` function to module level as `_generate_stream()`.

Replace `chat_stream()` with:

```python
@router.post("/stream")
@limiter.limit("30/minute")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream a chat response as Server-Sent Events."""
    llm = await get_llm_config(user=user, db=db, workspace_id=body.workspace_id)
    ctx = await build_chat_context(body, user, db, llm)

    logger.info(
        "chat_stream_started",
        user_id=str(user.id),
        conv_id=str(body.conversation_id),
        provider=llm.provider,
        model=llm.model_name,
    )

    return StreamingResponse(
        _generate_stream(ctx, llm, request, str(user.id)),
        media_type="text/event-stream",
    )
```

Move all content of the old inner `generate()` to a new module-level function `_generate_stream(ctx, llm, request, user_id_str)`.

The function signature:
```python
async def _generate_stream(  # noqa: C901
    ctx: ChatContext,
    llm: ResolvedLLMConfig,
    request: Request,
    user_id_str: str,
) -> AsyncGenerator[str]:
    ...
```

The body is identical to the old `generate()` — this is a pure extraction, not a rewrite.
Replace all `nonlocal` variable references to use `ctx.lc_messages`, `ctx.conv_id`, etc.

- [ ] **Step 2: Simplify `chat_regenerate()` using `build_chat_context()`**

`chat_regenerate()` currently duplicates ~150 lines of setup. After extracting `build_chat_context()`, replace its setup section:

```python
@router.post("/regenerate")
@limiter.limit("30/minute")
async def chat_regenerate(
    request: Request,
    body: RegenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Regenerate an AI response for an existing message."""
    from app.api.chat.schemas import ChatRequest as _CR

    llm = await get_llm_config(user=user, db=db, workspace_id=body.workspace_id)
    if body.model_override:
        from dataclasses import replace as dc_replace
        allowed = PROVIDER_MODELS.get(llm.provider, [])
        if allowed and body.model_override not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"model '{body.model_override}' not valid for '{llm.provider}'",
            )
        llm = dc_replace(llm, model_name=body.model_override)

    # Verify conversation and target message exist
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404)

    target_msg = await db.scalar(
        select(Message).where(
            Message.id == body.message_id,
            Message.conversation_id == conv.id,
        )
    )
    if not target_msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # Soft-delete the message being regenerated and its descendants
    await _soft_delete_message_subtree(db, target_msg)

    # Build context from the parent of the deleted message
    synthetic_request = _CR(
        conversation_id=body.conversation_id,
        content="",  # no new user message — regenerating from existing history
        parent_message_id=target_msg.parent_id,
        workspace_id=body.workspace_id,
    )
    ctx = await build_chat_context(synthetic_request, user, db, llm)

    return StreamingResponse(
        _generate_stream(ctx, llm, request, str(user.id)),
        media_type="text/event-stream",
    )
```

Note: `_soft_delete_message_subtree(db, target_msg)` is a new helper function extracted from the existing `chat_regenerate()` logic. It performs a soft-delete (sets `is_deleted=True`) on `target_msg` and all descendant messages that share `parent_id`. Add it as a module-level function in `routes.py`:

```python
async def _soft_delete_message_subtree(
    db: AsyncSession, root_msg: Message
) -> None:
    """Soft-delete root_msg and all messages that descend from it."""
    from sqlalchemy import update as sa_update
    # Collect all descendant IDs via iterative BFS
    to_delete = [root_msg.id]
    queue = [root_msg.id]
    while queue:
        current_id = queue.pop()
        rows = await db.scalars(
            select(Message.id).where(Message.parent_id == current_id)
        )
        children = list(rows.all())
        to_delete.extend(children)
        queue.extend(children)
    await db.execute(
        sa_update(Message)
        .where(Message.id.in_(to_delete))
        .values(is_deleted=True)
    )
    await db.commit()
```

- [ ] **Step 3: Update `tests/api/test_chat.py` mock targets**

Current mocks:
```python
# Old: mock deep inside generate()
patch("app.api.chat.routes.build_expert_graph", ...)
```

New mock target (patch at service boundary):
```python
# New: mock the module-level generator
patch("app.api.chat.routes._generate_stream", AsyncMock(...))
```

For tests that test `generate()` internals, update to test `_generate_stream()` with its new explicit parameters instead of relying on closure variables.

- [ ] **Step 4: Verify `chat_stream()` is ≤50 lines**

```bash
grep -n "async def chat_stream" backend/app/api/chat/routes.py
# Count lines until next @router.post or end of function
```
Expected: function body ≤50 lines.

- [ ] **Step 5: Run all chat tests**

```bash
cd backend && uv run pytest tests/api/test_chat*.py -v --tb=short
```
Expected: all pass.

- [ ] **Step 6: Run full test suite**

```bash
cd backend && uv run pytest tests/ -x -q --tb=short
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format && uv run mypy app
git add app/api/chat/routes.py tests/api/test_chat.py
git commit -m "refactor: simplify chat_stream() to ≤50 lines using build_chat_context()"
```

---

### Task 8: Final P1 verification

- [ ] **Step 1: Verify `create_graph()` call with `AgentConfig`**

```bash
cd backend && python -c "
from app.core.llm_config import AgentConfig, ResolvedLLMConfig
llm = ResolvedLLMConfig('deepseek', 'deepseek-chat', 'sk', ['sk'], None, None, {})
cfg = AgentConfig(llm=llm)
print('AgentConfig OK:', cfg)
"
```
Expected: prints config without errors.

- [ ] **Step 2: Check `chat_stream()` line count**

```bash
python3 -c "
import ast, sys
with open('backend/app/api/chat/routes.py') as f:
    src = f.read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.AsyncFunctionDef) and node.name == 'chat_stream':
        lines = node.end_lineno - node.lineno
        print(f'chat_stream: {lines} lines')
        assert lines <= 50, f'Still {lines} lines — target is ≤50'
"
```
Expected: `chat_stream: N lines` where N ≤ 50.

- [ ] **Step 3: Run full test suite**

```bash
cd backend && uv run pytest tests/ -x -q --tb=short
```
Expected: all pass.

- [ ] **Step 4: Push**

```bash
git push origin dev
```
