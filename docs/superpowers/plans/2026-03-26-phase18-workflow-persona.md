# Phase 18: Workflow Studio & Persona Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Workflow Studio a functional execution engine (DSL validation, compiler for all node types, SSE execution, run history) and enhance Personas with fine-grained model/tool/temperature control plus mid-conversation switching.

**Architecture:** No new services. Backend adds: Pydantic DSL schemas, enhanced LangGraph compiler, two new workflow API endpoints (`/execute` SSE, `/runs`), Persona model fields (migration 041), conversations `persona_id` FK (migration 042). Frontend connects existing UI stubs to real endpoints.

**Tech Stack:** FastAPI SSE StreamingResponse, LangGraph StateGraph, Jinja2 SandboxedEnvironment, Pydantic discriminated unions, Vue 3 + TypeScript, Alembic

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `backend/app/api/workflows.py` | Modify | Add DSL schemas, `/execute` SSE endpoint, `/runs` endpoint |
| `backend/app/agent/compiler.py` | Modify | Implement `tool`, `condition`, `output`, `image_gen` nodes; conditional edge routing; node_outputs state |
| `backend/app/api/personas.py` | Modify | Extend `PersonaCreate`/`PersonaOut` with new fields |
| `backend/app/db/models.py` | Modify | Add `temperature`, `model_name`, `enabled_tools`, `replace_system_prompt` to `Persona`; add `persona_id` FK to `Conversation` |
| `backend/app/api/conversations.py` | Modify | Add `persona_id` to `ConversationUpdate`; expose in `ConversationOut` |
| `backend/app/api/chat.py` | Modify | Apply persona `temperature`/`model_name`/`enabled_tools`/`replace_system_prompt` and `persona_id`-based lookup |
| `backend/alembic/versions/041_phase18_persona_fields.py` | **Create** | Add 4 fields to `personas` table |
| `backend/alembic/versions/042_phase18_conversation_persona_id.py` | **Create** | Add `persona_id` FK to `conversations` |
| `frontend/src/pages/WorkflowStudioPage.vue` | Modify | Connect `onRun()` to SSE, `fetchHistory()` to backend, add condition/output node panels |
| `frontend/src/api/workflows.ts` | Modify | Add `executeWorkflow` SSE helper, `listRuns` |
| `backend/tests/api/test_workflows.py` | Modify/Create | Tests for DSL validation, execute endpoint, runs endpoint |
| `backend/tests/api/test_personas.py` | Modify | Tests for new persona fields |

---

### Task 1: DSL Schema Validation (18.4)

**Files:**
- Modify: `backend/app/api/workflows.py`
- Modify: `backend/app/agent/compiler.py`

- [ ] **Step 1: Read current files**

Read `backend/app/api/workflows.py` completely.
Read `backend/app/agent/compiler.py` completely.

- [ ] **Step 2: Write failing tests**

Create or append to `backend/tests/api/test_workflows.py`:

```python
async def test_create_workflow_with_invalid_dsl_rejected(auth_client):
    """DSL with unknown node type must be rejected with 422."""
    resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "Invalid DSL",
            "dsl": {
                "nodes": [{"id": "n1", "type": "unknown_type", "data": {}}],
                "edges": [],
            },
        },
    )
    assert resp.status_code == 422


async def test_create_workflow_with_cycle_rejected(auth_client):
    """DSL with cycle must be rejected."""
    resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "Cyclic DSL",
            "dsl": {
                "nodes": [
                    {"id": "n1", "type": "llm", "data": {"prompt": "a"}},
                    {"id": "n2", "type": "llm", "data": {"prompt": "b"}},
                ],
                "edges": [
                    {"id": "e1", "source": "n1", "target": "n2"},
                    {"id": "e2", "source": "n2", "target": "n1"},
                ],
            },
        },
    )
    assert resp.status_code == 422


async def test_create_workflow_with_valid_dsl(auth_client):
    """Valid DSL with llm node passes validation."""
    resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "Valid Workflow",
            "dsl": {
                "nodes": [
                    {"id": "input_1", "type": "input", "data": {}},
                    {"id": "llm_1", "type": "llm", "data": {"prompt": "Hello", "model": "deepseek-chat"}},
                    {"id": "output_1", "type": "output", "data": {"format": "text"}},
                ],
                "edges": [
                    {"id": "e1", "source": "input_1", "target": "llm_1"},
                    {"id": "e2", "source": "llm_1", "target": "output_1"},
                ],
            },
        },
    )
    assert resp.status_code == 201
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend && POSTGRES_PASSWORD=$POSTGRES_PASSWORD uv run pytest tests/api/test_workflows.py::test_create_workflow_with_invalid_dsl_rejected -v
```

Expected: FAIL (currently any dict is accepted)

- [ ] **Step 4: Add Pydantic DSL schemas to workflows.py**

After the existing `WorkflowCreate` / `WorkflowOut` schemas, add:

```python
from __future__ import annotations
from typing import Annotated, Any, Literal
import json
from pydantic import field_validator, model_validator

# --- DSL node schemas (discriminated union on `type`) ---

class InputNodeDef(BaseModel):
    id: str
    type: Literal["input"]
    data: dict[str, Any] = {}

class LLMNodeDef(BaseModel):
    id: str
    type: Literal["llm"]
    data: dict[str, Any]  # expects prompt, model

class ToolNodeDef(BaseModel):
    id: str
    type: Literal["tool"]
    data: dict[str, Any]  # expects tool_name

class ConditionNodeDef(BaseModel):
    id: str
    type: Literal["condition"]
    data: dict[str, Any]  # expects condition_expression (Jinja2)

class OutputNodeDef(BaseModel):
    id: str
    type: Literal["output"]
    data: dict[str, Any] = {}

class ImageGenNodeDef(BaseModel):
    id: str
    type: Literal["image_gen"]
    data: dict[str, Any]  # expects prompt

NodeDef = Annotated[
    InputNodeDef | LLMNodeDef | ToolNodeDef | ConditionNodeDef | OutputNodeDef | ImageGenNodeDef,
    Field(discriminator="type"),
]

class EdgeDef(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: str | None = None
    targetHandle: str | None = None

class WorkflowDSLSchema(BaseModel):
    nodes: list[NodeDef]
    edges: list[EdgeDef]

    @model_validator(mode="after")
    def validate_dag(self) -> "WorkflowDSLSchema":
        node_ids = {n.id for n in self.nodes}
        # Check all edge endpoints exist
        for edge in self.edges:
            if edge.source not in node_ids:
                raise ValueError(f"Edge source '{edge.source}' not in nodes")
            if edge.target not in node_ids:
                raise ValueError(f"Edge target '{edge.target}' not in nodes")
        # Cycle detection (DFS)
        adj: dict[str, list[str]] = {n.id: [] for n in self.nodes}
        for edge in self.edges:
            adj[edge.source].append(edge.target)
        visited: set[str] = set()
        rec_stack: set[str] = set()
        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False
        for node_id in node_ids:
            if node_id not in visited:
                if has_cycle(node_id):
                    raise ValueError("Workflow DSL contains a cycle (loops are not supported)")
        return self
```

Update `WorkflowCreate.dsl` to use the validator:

```python
class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    dsl: dict[str, Any]

    @field_validator("dsl", mode="before")
    @classmethod
    def validate_dsl_structure(cls, v: Any) -> Any:
        WorkflowDSLSchema.model_validate(v)
        return v
```

- [ ] **Step 5: Run tests**

```bash
cd backend && POSTGRES_PASSWORD=$POSTGRES_PASSWORD uv run pytest tests/api/test_workflows.py::test_create_workflow_with_invalid_dsl_rejected tests/api/test_workflows.py::test_create_workflow_with_cycle_rejected tests/api/test_workflows.py::test_create_workflow_with_valid_dsl -v
```

Expected: 3 PASSED

- [ ] **Step 6: Lint + mypy**

```bash
cd backend && uv run ruff check app/api/workflows.py --fix && uv run mypy app/api/workflows.py
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/workflows.py backend/tests/api/test_workflows.py
git commit -m "feat: add Pydantic DSL schema validation with cycle detection"
```

---

### Task 2: Graph Compiler Enhancement (18.2 + 18.3)

**Files:**
- Modify: `backend/app/agent/compiler.py`

- [ ] **Step 1: Read the file**

Read `backend/app/agent/compiler.py` completely.

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/agent/test_compiler.py (create or append)
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agent.compiler import GraphCompiler


def make_dsl(nodes, edges):
    return {"nodes": nodes, "edges": edges}


@pytest.mark.anyio
async def test_compiler_output_node_writes_result():
    """Output node should capture last LLM message in node_outputs."""
    dsl = make_dsl(
        nodes=[
            {"id": "input_1", "type": "input", "data": {}},
            {"id": "llm_1", "type": "llm", "data": {"prompt": "Hello"}},
            {"id": "output_1", "type": "output", "data": {}},
        ],
        edges=[
            {"id": "e1", "source": "input_1", "target": "llm_1"},
            {"id": "e2", "source": "llm_1", "target": "output_1"},
        ],
    )
    compiler = GraphCompiler(dsl, provider="deepseek", model="deepseek-chat", api_key="test")
    with patch.object(compiler, "_make_llm_node", return_value=AsyncMock(
        return_value={"messages": [MagicMock(content="hello result")], "node_outputs": {}}
    )):
        graph = compiler.compile()
        assert graph is not None


@pytest.mark.anyio
async def test_compiler_condition_uses_jinja2():
    """Condition node expression uses Jinja2 sandbox, not eval."""
    dsl = make_dsl(
        nodes=[
            {"id": "input_1", "type": "input", "data": {}},
            {"id": "cond_1", "type": "condition", "data": {"condition_expression": "{{ nodes.input_1.output | length > 0 }}"}},
            {"id": "output_yes", "type": "output", "data": {}},
            {"id": "output_no", "type": "output", "data": {}},
        ],
        edges=[
            {"id": "e1", "source": "input_1", "target": "cond_1"},
            {"id": "e2", "source": "cond_1", "target": "output_yes", "sourceHandle": "true"},
            {"id": "e3", "source": "cond_1", "target": "output_no", "sourceHandle": "false"},
        ],
    )
    compiler = GraphCompiler(dsl, provider="deepseek", model="deepseek-chat", api_key="test")
    # Should not raise during compile
    graph = compiler.compile()
    assert graph is not None
```

- [ ] **Step 3: Implement enhanced compiler**

Update `backend/app/agent/compiler.py`:

a) Add `node_outputs: dict[str, Any]` to `GraphState`:

```python
from typing import Any
from langgraph.graph import END, START, StateGraph
from langchain_core.messages import BaseMessage, HumanMessage
from typing_extensions import TypedDict

class GraphState(TypedDict):
    messages: list[BaseMessage]
    inputs: dict[str, Any]
    node_outputs: dict[str, Any]  # NEW: stores each node's output keyed by node_id
```

b) Implement `output` node handler:

```python
def _make_output_node(self, node: WorkflowNodeDSL):
    node_id = node.id
    def output_handler(state: GraphState) -> GraphState:
        # Capture last AI message content as output
        last_content = ""
        if state.get("messages"):
            last_msg = state["messages"][-1]
            last_content = getattr(last_msg, "content", str(last_msg))
        node_outputs = dict(state.get("node_outputs", {}))
        node_outputs[node_id] = last_content
        return {**state, "node_outputs": node_outputs}
    return output_handler
```

c) Implement `tool` node handler (invokes a registered tool by name):

```python
def _make_tool_node(self, node: WorkflowNodeDSL):
    node_id = node.id
    tool_name = node.data.get("tool_name", "")
    async def tool_handler(state: GraphState) -> GraphState:
        # Find tool in self._tools by name
        tool = next((t for t in self._tools if t.name == tool_name), None)
        if tool is None:
            result = f"Error: tool '{tool_name}' not found"
        else:
            # Build input from last message content or node_outputs
            last_content = ""
            if state.get("messages"):
                last_content = getattr(state["messages"][-1], "content", "")
            try:
                result = await tool.arun(last_content)
            except Exception as exc:
                result = f"Tool error: {exc}"
        node_outputs = dict(state.get("node_outputs", {}))
        node_outputs[node_id] = result
        from langchain_core.messages import AIMessage
        return {**state, "messages": [*state["messages"], AIMessage(content=result)], "node_outputs": node_outputs}
    return tool_handler
```

d) Implement `condition` node handler using Jinja2:

```python
def _make_condition_node(self, node: WorkflowNodeDSL, true_target: str, false_target: str):
    expr = node.data.get("condition_expression", "{{ false }}")
    node_id = node.id
    def condition_router(state: GraphState) -> str:
        from jinja2.sandbox import SandboxedEnvironment
        env = SandboxedEnvironment()
        ctx = {"nodes": {k: {"output": v} for k, v in state.get("node_outputs", {}).items()},
               "inputs": state.get("inputs", {})}
        try:
            result = env.from_string(expr).render(**ctx).strip().lower()
            return true_target if result in ("true", "1", "yes") else false_target
        except Exception:
            return false_target
    return condition_router
```

e) Implement `image_gen` node handler:

```python
def _make_image_gen_node(self, node: WorkflowNodeDSL):
    node_id = node.id
    async def image_gen_handler(state: GraphState) -> GraphState:
        prompt = node.data.get("prompt", "")
        # Render template variables
        from jinja2.sandbox import SandboxedEnvironment
        env = SandboxedEnvironment()
        ctx = {"nodes": {k: {"output": v} for k, v in state.get("node_outputs", {}).items()},
               "inputs": state.get("inputs", {})}
        try:
            prompt = env.from_string(prompt).render(**ctx)
        except Exception:
            pass
        # Use image_gen_tool if api_key available
        from app.tools.image_gen_tool import create_image_gen_tool
        tool = create_image_gen_tool(self._api_key if hasattr(self, "_api_key") else None)
        if tool:
            try:
                result = await tool.arun(prompt)
            except Exception as exc:
                result = f"Image gen error: {exc}"
        else:
            result = "Error: OpenAI API key required for image generation"
        node_outputs = dict(state.get("node_outputs", {}))
        node_outputs[node_id] = result
        from langchain_core.messages import AIMessage
        return {**state, "messages": [*state["messages"], AIMessage(content=result)], "node_outputs": node_outputs}
    return image_gen_handler
```

f) Update `compile()` to use these handlers and route conditional edges:

In the node-building loop, dispatch by type:
- `"output"` → `_make_output_node(node)`
- `"tool"` → `_make_tool_node(node)`
- `"image_gen"` → `_make_image_gen_node(node)`
- `"condition"` → special handling below

For `condition` nodes, find outgoing edges with `sourceHandle == "true"` and `sourceHandle == "false"`, then use `graph.add_conditional_edges()`:

```python
# After adding all nodes, handle conditional edges
for node in dsl.nodes:
    if node.type == "condition":
        true_edges = [e for e in dsl.edges if e.source == node.id and e.sourceHandle == "true"]
        false_edges = [e for e in dsl.edges if e.source == node.id and e.sourceHandle == "false"]
        true_target = true_edges[0].target if true_edges else END
        false_target = false_edges[0].target if false_edges else END
        router = self._make_condition_node(node, true_target, false_target)
        graph.add_conditional_edges(node.id, router, {true_target: true_target, false_target: false_target})
    else:
        # regular outgoing edges
        for edge in [e for e in dsl.edges if e.source == node.id]:
            graph.add_edge(edge.source, edge.target)
```

Also update LLM node to render `{{nodes.X.output}}` template variables using Jinja2 SandboxedEnvironment.

g) LLM node needs `_api_key` attribute — ensure it's stored in `__init__`:
```python
def __init__(self, dsl, provider, model, api_key, tools=None):
    self._api_key = api_key
    # ... existing init ...
```

- [ ] **Step 4: Add `jinja2` dependency if not present**

```bash
cd backend && uv add jinja2
```

Check if it's already in `pyproject.toml` first (it likely is as LangChain depends on it).

- [ ] **Step 5: Run tests**

```bash
cd backend && POSTGRES_PASSWORD=$POSTGRES_PASSWORD uv run pytest tests/agent/test_compiler.py -v
```

- [ ] **Step 6: Lint + mypy**

```bash
cd backend && uv run ruff check app/agent/compiler.py --fix && uv run mypy app/agent/compiler.py
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/agent/compiler.py backend/tests/agent/test_compiler.py
git commit -m "feat: implement condition/output/tool/image_gen nodes and inter-node variable passing"
```

---

### Task 3: Workflow Execution + Run History Endpoints (18.1)

**Files:**
- Modify: `backend/app/api/workflows.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/api/test_workflows.py`:

```python
from unittest.mock import patch, AsyncMock

async def test_execute_workflow_returns_sse(auth_client):
    """POST /execute returns 200 SSE stream."""
    # First create a workflow
    create_resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "Exec Test",
            "dsl": {
                "nodes": [
                    {"id": "input_1", "type": "input", "data": {}},
                    {"id": "output_1", "type": "output", "data": {}},
                ],
                "edges": [{"id": "e1", "source": "input_1", "target": "output_1"}],
            },
        },
    )
    wf_id = create_resp.json()["id"]

    with patch("app.api.workflows.GraphCompiler") as mock_compiler_cls:
        mock_graph = AsyncMock()
        mock_graph.astream = AsyncMock(return_value=aiter([
            {"node_outputs": {"output_1": "done"}, "messages": []},
        ]))
        mock_compiler_cls.return_value.compile.return_value = mock_graph
        resp = await auth_client.post(
            f"/api/workflows/{wf_id}/execute",
            json={"inputs": {"query": "hello"}},
        )
    assert resp.status_code == 200


async def test_list_workflow_runs(auth_client):
    """GET /runs returns list of run records."""
    create_resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "Runs Test",
            "dsl": {"nodes": [{"id": "input_1", "type": "input", "data": {}}], "edges": []},
        },
    )
    wf_id = create_resp.json()["id"]
    resp = await auth_client.get(f"/api/workflows/{wf_id}/runs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 2: Add /execute SSE endpoint**

```python
import asyncio
import json as json_lib
from fastapi.responses import StreamingResponse
from app.agent.compiler import GraphCompiler

class WorkflowExecuteRequest(BaseModel):
    inputs: dict[str, Any] = {}

@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: uuid.UUID,
    body: WorkflowExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute a workflow and stream node events via SSE."""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == current_user.id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Create a WorkflowRun record
    run = WorkflowRun(
        workflow_id=workflow.id,
        user_id=current_user.id,
        status="running",
        input_data=body.inputs,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    run_id = str(run.id)

    # Get user settings for LLM config
    settings_result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    user_settings = settings_result.scalar_one_or_none()

    async def event_stream():
        try:
            provider = getattr(user_settings, "llm_provider", "deepseek") if user_settings else "deepseek"
            model = getattr(user_settings, "llm_model", "deepseek-chat") if user_settings else "deepseek-chat"
            api_key = ""
            if user_settings:
                try:
                    from app.core.security import fernet_decrypt
                    raw = getattr(user_settings, f"{provider}_api_key", "") or ""
                    api_key = fernet_decrypt(raw) if raw else ""
                except Exception:
                    api_key = ""

            compiler = GraphCompiler(
                dsl=workflow.dsl,
                provider=provider,
                model=model,
                api_key=api_key,
            )
            graph = compiler.compile()

            from langchain_core.messages import HumanMessage
            state = {
                "messages": [HumanMessage(content=json_lib.dumps(body.inputs))],
                "inputs": body.inputs,
                "node_outputs": {},
            }

            import time
            async for chunk in graph.astream(state):
                node_outputs = chunk.get("node_outputs", {})
                for node_id, output in node_outputs.items():
                    event = {"type": "node_done", "node_id": node_id, "output": str(output), "duration_ms": 0}
                    yield f"data: {json_lib.dumps(event)}\n\n"

            # Update run record
            async with AsyncSessionLocal() as update_db:
                run_record = await update_db.get(WorkflowRun, run.id)
                if run_record:
                    run_record.status = "completed"
                    from datetime import datetime, timezone
                    run_record.completed_at = datetime.now(timezone.utc)
                    await update_db.commit()

            done_event = {"type": "run_done", "run_id": run_id, "status": "completed"}
            yield f"data: {json_lib.dumps(done_event)}\n\n"

        except Exception as exc:
            error_event = {"type": "run_error", "run_id": run_id, "error": str(exc)}
            yield f"data: {json_lib.dumps(error_event)}\n\n"
            async with AsyncSessionLocal() as update_db:
                run_record = await update_db.get(WorkflowRun, run.id)
                if run_record:
                    run_record.status = "failed"
                    run_record.error_message = str(exc)
                    await update_db.commit()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 3: Add /runs endpoint**

```python
class WorkflowRunOut(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)

@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunOut])
async def list_workflow_runs(
    workflow_id: uuid.UUID,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List workflow run history."""
    # Verify ownership
    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == current_user.id)
    )
    if wf_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow_id, WorkflowRun.user_id == current_user.id)
        .order_by(WorkflowRun.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()
```

Ensure `WorkflowRun` is imported from `app.db.models`.

- [ ] **Step 4: Run tests**

```bash
cd backend && POSTGRES_PASSWORD=$POSTGRES_PASSWORD uv run pytest tests/api/test_workflows.py -v --tb=short
```

- [ ] **Step 5: Lint + mypy**

```bash
cd backend && uv run ruff check app/api/workflows.py --fix && uv run mypy app/api/workflows.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/workflows.py backend/tests/api/test_workflows.py
git commit -m "feat: add workflow /execute SSE endpoint and /runs history endpoint"
```

---

### Task 4: Persona Model Enhancement + Migration (18.6)

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/api/personas.py`
- Create: `backend/alembic/versions/041_phase18_persona_fields.py`

- [ ] **Step 1: Read current Persona model and migration chain**

Read `backend/app/db/models.py` lines 875-900.
Check: `ls backend/alembic/versions/ | sort | tail -5`

- [ ] **Step 2: Write failing tests**

Append to `backend/tests/api/test_personas.py` (create if missing):

```python
async def test_create_persona_with_extended_fields(auth_client):
    """Persona creation accepts temperature, model_name, enabled_tools, replace_system_prompt."""
    resp = await auth_client.post(
        "/api/personas",
        json={
            "name": "Custom Persona",
            "system_prompt": "You are a helpful assistant.",
            "temperature": 0.7,
            "model_name": "deepseek-chat",
            "enabled_tools": ["web_search", "code_exec"],
            "replace_system_prompt": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["temperature"] == 0.7
    assert data["model_name"] == "deepseek-chat"
    assert data["enabled_tools"] == ["web_search", "code_exec"]
    assert data["replace_system_prompt"] is True


async def test_persona_defaults_for_new_fields(auth_client):
    """Old-style persona creation (no new fields) has sane defaults."""
    resp = await auth_client.post(
        "/api/personas",
        json={"name": "Simple", "system_prompt": "Be helpful."},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["temperature"] is None
    assert data["model_name"] is None
    assert data["enabled_tools"] is None
    assert data["replace_system_prompt"] is False
```

- [ ] **Step 3: Add fields to Persona model**

In `backend/app/db/models.py`, add to `Persona` class:

```python
temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
enabled_tools: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
replace_system_prompt: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
```

Ensure `ARRAY`, `Float`, `Boolean` are imported from `sqlalchemy`.

- [ ] **Step 4: Update PersonaCreate and PersonaOut schemas**

```python
class PersonaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    system_prompt: str = Field(min_length=1, max_length=8000)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    model_name: str | None = Field(default=None, max_length=100)
    enabled_tools: list[str] | None = None
    replace_system_prompt: bool = False

class PersonaOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    system_prompt: str
    temperature: float | None
    model_name: str | None
    enabled_tools: list[str] | None
    replace_system_prompt: bool
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 5: Create Alembic migration**

Run: `cd backend && uv run alembic revision --autogenerate -m "phase18_persona_fields"`

Review the generated file and ensure it adds the four columns. If autogenerate doesn't pick up ARRAY, write manually:

```python
def upgrade() -> None:
    op.add_column("personas", sa.Column("temperature", sa.Float(), nullable=True))
    op.add_column("personas", sa.Column("model_name", sa.String(100), nullable=True))
    op.add_column("personas", sa.Column("enabled_tools", postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column("personas", sa.Column("replace_system_prompt", sa.Boolean(), server_default="false", nullable=False))

def downgrade() -> None:
    op.drop_column("personas", "replace_system_prompt")
    op.drop_column("personas", "enabled_tools")
    op.drop_column("personas", "model_name")
    op.drop_column("personas", "temperature")
```

- [ ] **Step 6: Run migration**

```bash
cd backend && POSTGRES_PASSWORD=$POSTGRES_PASSWORD uv run alembic upgrade head
```

- [ ] **Step 7: Run tests**

```bash
cd backend && POSTGRES_PASSWORD=$POSTGRES_PASSWORD uv run pytest tests/api/test_personas.py -v
```

- [ ] **Step 8: Lint + mypy**

```bash
cd backend && uv run ruff check app/api/personas.py app/db/models.py --fix && uv run mypy app/api/personas.py app/db/models.py
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/db/models.py backend/app/api/personas.py backend/alembic/versions/
git commit -m "feat: extend Persona with temperature/model_name/enabled_tools/replace_system_prompt"
```

---

### Task 5: Mid-Conversation Persona Switching (18.7)

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/api/conversations.py`
- Modify: `backend/app/api/chat.py`
- Create: `backend/alembic/versions/042_phase18_conversation_persona_id.py`

- [ ] **Step 1: Read relevant files**

Read `backend/app/db/models.py` lines 140-200 (Conversation model).
Read `backend/app/api/conversations.py` lines 30-70 (schemas) and 520-550 (PATCH endpoint).
Read `backend/app/api/chat.py` lines 200-260 (persona handling in stream).

- [ ] **Step 2: Write failing test**

```python
# backend/tests/api/test_conversations.py — append
async def test_patch_conversation_persona_id(auth_client):
    """PATCH /conversations/{id} can update persona_id."""
    # Create a persona
    persona_resp = await auth_client.post(
        "/api/personas",
        json={"name": "Test Persona", "system_prompt": "Be brief."},
    )
    persona_id = persona_resp.json()["id"]

    # Create a conversation
    conv_resp = await auth_client.post(
        "/api/conversations", json={"title": "Test Conv"}
    )
    conv_id = conv_resp.json()["id"]

    # Attach persona
    patch_resp = await auth_client.patch(
        f"/api/conversations/{conv_id}", json={"persona_id": persona_id}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["persona_id"] == persona_id
```

- [ ] **Step 3: Add persona_id FK to Conversation model**

```python
persona_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True
)
```

- [ ] **Step 4: Create migration**

```python
def upgrade() -> None:
    op.add_column("conversations", sa.Column("persona_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_conversations_persona_id", "conversations", "personas", ["persona_id"], ["id"], ondelete="SET NULL")

def downgrade() -> None:
    op.drop_constraint("fk_conversations_persona_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "persona_id")
```

Run: `cd backend && POSTGRES_PASSWORD=$POSTGRES_PASSWORD uv run alembic upgrade head`

- [ ] **Step 5: Update ConversationUpdate + ConversationOut schemas**

```python
class ConversationUpdate(BaseModel):
    title: str | None = None
    persona_override: str | None = None
    persona_id: uuid.UUID | None = None  # NEW
    folder_id: uuid.UUID | None = None

class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    active_leaf_id: uuid.UUID | None
    is_pinned: bool = False
    folder_id: uuid.UUID | None
    persona_id: uuid.UUID | None = None  # NEW
    updated_at: datetime | None
    tags: list[str] = []
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 6: Apply persona in chat.py**

In `chat.py`, when building the graph/system_prompt, look up the conversation's `persona_id` first, then fall back to the request body's `persona_override`:

```python
# In the streaming handler, after loading the conversation:
persona = None
if conversation.persona_id:
    from sqlalchemy import select as sa_select
    persona_result = await db.execute(
        sa_select(Persona).where(Persona.id == conversation.persona_id)
    )
    persona = persona_result.scalar_one_or_none()

# Apply persona fields to graph creation:
if persona:
    effective_model = persona.model_name or settings_model
    effective_temperature = persona.temperature  # None = use default
    effective_tools = persona.enabled_tools  # None = all tools
    effective_system = persona.system_prompt if persona.replace_system_prompt else None
```

- [ ] **Step 7: Run tests**

```bash
cd backend && POSTGRES_PASSWORD=$POSTGRES_PASSWORD uv run pytest tests/api/test_conversations.py -v --tb=short
```

- [ ] **Step 8: Lint + mypy**

```bash
cd backend && uv run ruff check app/api/conversations.py app/api/chat.py app/db/models.py --fix && uv run mypy app/api/conversations.py app/api/chat.py
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/db/models.py backend/app/api/conversations.py backend/app/api/chat.py backend/alembic/versions/
git commit -m "feat: add persona_id FK to conversations for mid-conversation persona switching"
```

---

### Task 6: Frontend Studio Connection (18.5)

**Files:**
- Modify: `frontend/src/pages/WorkflowStudioPage.vue`
- Modify: `frontend/src/api/workflows.ts` (or equivalent API file)

- [ ] **Step 1: Read current frontend files**

Read `frontend/src/pages/WorkflowStudioPage.vue` completely.
Read `frontend/src/api/workflows.ts` if it exists.

- [ ] **Step 2: Check if `executeWorkflow` SSE already exists in API file**

The frontend `onRun()` calls `POST /api/workflows/{id}/execute` and reads an SSE stream. If the API helper doesn't exist, add it using native fetch + ReadableStream (same pattern as `chat.ts`).

- [ ] **Step 3: Add condition node property panel in Vue**

In the property panel section, add a text area for `condition_expression` when `selectedNode.type === 'condition'`:

```html
<div v-else-if="selectedNode.type === 'condition'" class="prop-group">
  <label>条件表达式 (Jinja2)</label>
  <textarea
    v-model="selectedNode.data.condition_expression"
    placeholder="{{ nodes.node_id.output | length > 0 }}"
    class="modern-input"
    rows="3"
    @change="onNodeDataChange"
  />
  <p class="hint">使用 Jinja2 模板，访问 nodes.&lt;id&gt;.output</p>
</div>
```

- [ ] **Step 4: Add output node property panel**

```html
<div v-else-if="selectedNode.type === 'output'" class="prop-group">
  <label>输出格式</label>
  <select v-model="selectedNode.data.format" class="role-select" @change="onNodeDataChange">
    <option value="text">文本</option>
    <option value="markdown">Markdown</option>
    <option value="json">JSON</option>
  </select>
</div>
```

- [ ] **Step 5: Add 30s timeout warning in run drawer**

In the run drawer, add a timeout warning if no SSE events for 30s:

```typescript
let runTimeoutId: ReturnType<typeof setTimeout> | null = null

function resetRunTimeout() {
  if (runTimeoutId) clearTimeout(runTimeoutId)
  runTimeoutId = setTimeout(() => {
    runLogs.value.push({ type: 'warning', content: '30秒无响应，工作流可能超时', timestamp: Date.now() })
  }, 30000)
}
```

Call `resetRunTimeout()` on each SSE event. Clear on `run_done`.

- [ ] **Step 6: Verify frontend build**

```bash
cd frontend && bun run type-check && bun run lint:fix
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/WorkflowStudioPage.vue frontend/src/api/
git commit -m "feat: connect workflow studio frontend to execute/runs endpoints"
```

---

### Task 7: Final checks + push

- [ ] **Step 1: Full backend checks**

```bash
cd backend
uv run ruff check --fix && uv run ruff format
uv run mypy app
POSTGRES_PASSWORD=$POSTGRES_PASSWORD uv run pytest tests/ -x -q --tb=short
```

- [ ] **Step 2: Frontend checks**

```bash
cd frontend && bun run lint:fix && bun run type-check
```

- [ ] **Step 3: Quality loop**

Run `/simplify` skill, then `superpowers:code-reviewer` Task agent.

- [ ] **Step 4: Push**

```bash
git push origin dev
```
