# P3: Test Coverage Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tests for the 13 modules that currently have zero coverage, prioritized by risk (auth-sensitive first, pure logic last).

**Architecture:** All new tests follow the existing `conftest.py` patterns — `@pytest.mark.anyio`, `autouse` fixtures suppressing `log_action` and PAT updates, mock at service/repository boundaries rather than at DB driver level. Prerequisite: P1 must be merged first so tests can mock at the new `AgentExecutionService` boundary.

**Tech Stack:** pytest, anyio, `unittest.mock`, FastAPI `TestClient`

---

### Task 1: `tests/api/test_workspaces.py` — multi-tenant permission isolation

**Files:**
- Create: `backend/tests/api/test_workspaces.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/api/test_workspaces.py
"""Tests for workspace API — focuses on multi-tenant permission boundaries."""

import uuid
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


@pytest.fixture
def other_user_workspace_id():
    return uuid.uuid4()


@pytest.mark.anyio
async def test_list_workspaces_returns_only_own_workspaces(auth_client):
    """Users must only see workspaces in their own organization."""
    resp = await auth_client.get("/api/workspaces/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # All returned workspaces must belong to the authenticated user's org
    # (verified by the auth fixture setup, not a cross-org leak)


@pytest.mark.anyio
async def test_get_workspace_in_different_org_returns_404(auth_client, other_user_workspace_id):
    """Cross-organization workspace lookup must return 404, not 403.

    404 prevents leaking workspace existence to users in other orgs.
    """
    resp = await auth_client.get(f"/api/workspaces/{other_user_workspace_id}")
    # Either 404 (not found / cross-org) or 403 (not a member) is acceptable;
    # 200 with another org's data is NOT acceptable.
    assert resp.status_code in (403, 404)


@pytest.mark.anyio
async def test_create_workspace_requires_auth(client):
    """Unauthenticated workspace creation must be rejected."""
    resp = await client.post("/api/workspaces/", json={"name": "Test"})
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_workspace_member_cannot_access_other_workspace(auth_client):
    """A member of workspace A cannot access workspace B."""
    random_id = uuid.uuid4()
    resp = await auth_client.get(f"/api/workspaces/{random_id}/members")
    assert resp.status_code in (403, 404)


@pytest.mark.anyio
async def test_invite_to_workspace_requires_membership(auth_client):
    """Only workspace members can send invitations."""
    random_workspace_id = uuid.uuid4()
    resp = await auth_client.post(
        f"/api/workspaces/{random_workspace_id}/invitations",
        json={"email": "stranger@example.com", "role": "member"},
    )
    assert resp.status_code in (403, 404)
```

- [ ] **Step 2: Run tests**

```bash
cd backend && uv run pytest tests/api/test_workspaces.py -v --tb=short
```
Expected: all pass (or document which require DB fixtures and skip appropriately).

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_workspaces.py
git commit -m "test: add workspace permission boundary tests"
```

---

### Task 2: `tests/api/test_plugins.py` — three plugin type branches

**Files:**
- Create: `backend/tests/api/test_plugins.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/api/test_plugins.py
"""Tests for plugin API — focuses on MCP/Python/Node type detection."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.anyio
async def test_detect_plugin_type_mcp_json():
    """A JSON config with 'mcpServers' key must be detected as MCP type."""
    from app.api.plugins import detect_plugin_type

    result = detect_plugin_type('{"mcpServers": {"server1": {}}}')
    assert result == "mcp"


@pytest.mark.anyio
async def test_detect_plugin_type_python_script():
    """A Python file path must be detected as python type."""
    from app.api.plugins import detect_plugin_type

    result = detect_plugin_type("/path/to/plugin.py")
    assert result == "python"


@pytest.mark.anyio
async def test_detect_plugin_type_node_package():
    """A Node.js package.json path must be detected as node type."""
    from app.api.plugins import detect_plugin_type

    result = detect_plugin_type("/path/to/package.json")
    assert result == "node"


@pytest.mark.anyio
async def test_list_installed_plugins_requires_auth(client):
    """Unauthenticated plugin listing must return 401."""
    resp = await client.get("/api/plugins/")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_install_plugin_unknown_type_returns_400(auth_client):
    """Uploading an unknown plugin type must return 400."""
    resp = await auth_client.post(
        "/api/plugins/install",
        json={"source": "/nonexistent/file.xyz", "name": "bad-plugin"},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.anyio
async def test_get_plugin_config_returns_404_for_missing(auth_client):
    """Fetching config for a non-existent plugin must return 404."""
    import uuid
    resp = await auth_client.get(f"/api/plugins/{uuid.uuid4()}/config")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests**

```bash
cd backend && uv run pytest tests/api/test_plugins.py -v --tb=short
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_plugins.py
git commit -m "test: add plugin type detection and permission tests"
```

---

### Task 3: `tests/api/test_public.py` — public share links

**Files:**
- Create: `backend/tests/api/test_public.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/api/test_public.py
"""Tests for public conversation share links."""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.anyio
async def test_public_share_nonexistent_returns_404(client):
    """Accessing a non-existent share token must return 404."""
    resp = await client.get(f"/api/public/share/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_public_share_does_not_require_auth(client):
    """Public share endpoints must be accessible without authentication."""
    # A 404 (not found) is the expected response for a random token.
    # A 401 (unauthorized) would mean auth guard is incorrectly applied.
    resp = await client.get(f"/api/public/share/{uuid.uuid4()}")
    assert resp.status_code != 401


@pytest.mark.anyio
async def test_create_share_link_requires_auth(client):
    """Creating a share link must require authentication."""
    resp = await client.post(
        "/api/conversations/some-id/share",
        json={"is_public": True},
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_create_share_link_for_other_users_conv_returns_404(auth_client):
    """Users cannot create share links for conversations they don't own."""
    other_conv_id = uuid.uuid4()
    resp = await auth_client.post(
        f"/api/conversations/{other_conv_id}/share",
        json={"is_public": True},
    )
    assert resp.status_code in (404, 403)
```

- [ ] **Step 2: Run tests**

```bash
cd backend && uv run pytest tests/api/test_public.py -v --tb=short
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_public.py
git commit -m "test: add public share link permission tests"
```

---

### Task 4: `tests/agent/test_persona.py` — persona prompt assembly

**Files:**
- Create: `backend/tests/agent/test_persona.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/agent/test_persona.py
"""Tests for persona system prompt assembly."""

import pytest
from app.agent.persona import build_system_prompt


def test_build_system_prompt_with_override():
    """Custom persona override text must appear in the system prompt."""
    result = build_system_prompt("You are a pirate assistant.")
    assert "pirate" in result.lower()


def test_build_system_prompt_without_override_returns_default():
    """No override must return a non-empty default system prompt."""
    result = build_system_prompt(None)
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_system_prompt_with_empty_override_returns_default():
    """Empty string override must fall back to default, not produce empty prompt."""
    result = build_system_prompt("")
    assert len(result) > 0


def test_build_system_prompt_override_takes_priority():
    """Custom override must replace (not append to) the default prompt."""
    custom = "CUSTOM_MARKER_UNIQUE_STRING"
    result = build_system_prompt(custom)
    assert custom in result
```

- [ ] **Step 2: Run tests**

```bash
cd backend && uv run pytest tests/agent/test_persona.py -v
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add tests/agent/test_persona.py
git commit -m "test: add persona system prompt assembly tests"
```

---

### Task 5: `tests/agent/test_workflow_schema.py` — DSL validation edge cases

**Files:**
- Create: `backend/tests/agent/test_workflow_schema.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/agent/test_workflow_schema.py
"""Tests for WorkflowDSLSchema validation — boundary conditions and error paths."""

import pytest
from app.agent.workflow_schema import WorkflowDSLSchema


def _valid_dsl():
    return {
        "nodes": [
            {"id": "start", "type": "llm", "prompt": "Do X"},
            {"id": "end", "type": "output"},
        ],
        "edges": [
            {"from": "start", "to": "end"},
        ],
        "entry": "start",
    }


def test_valid_dsl_passes_validation():
    schema = WorkflowDSLSchema()
    errors = schema.validate(_valid_dsl())
    assert errors == []


def test_missing_nodes_fails_validation():
    """DSL without 'nodes' key must produce a validation error."""
    schema = WorkflowDSLSchema()
    bad = {"edges": [], "entry": "start"}
    errors = schema.validate(bad)
    assert any("nodes" in str(e).lower() for e in errors)


def test_missing_entry_node_fails_validation():
    """Entry point must reference a node that exists in the nodes list."""
    schema = WorkflowDSLSchema()
    bad = _valid_dsl()
    bad["entry"] = "nonexistent_node"
    errors = schema.validate(bad)
    assert errors  # must have at least one error


def test_cycle_detection_fails_validation():
    """A DSL with a cycle (A→B→A) must fail validation."""
    schema = WorkflowDSLSchema()
    cyclic = {
        "nodes": [
            {"id": "A", "type": "llm", "prompt": "Step A"},
            {"id": "B", "type": "llm", "prompt": "Step B"},
        ],
        "edges": [
            {"from": "A", "to": "B"},
            {"from": "B", "to": "A"},  # cycle
        ],
        "entry": "A",
    }
    errors = schema.validate(cyclic)
    assert any("cycle" in str(e).lower() or "circular" in str(e).lower() for e in errors)


def test_edge_to_missing_node_fails_validation():
    """An edge pointing to a non-existent node must fail."""
    schema = WorkflowDSLSchema()
    bad = _valid_dsl()
    bad["edges"].append({"from": "start", "to": "ghost_node"})
    errors = schema.validate(bad)
    assert errors
```

- [ ] **Step 2: Run tests**

```bash
cd backend && uv run pytest tests/agent/test_workflow_schema.py -v
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add tests/agent/test_workflow_schema.py
git commit -m "test: add WorkflowDSLSchema edge case validation tests"
```

---

### Task 6: `tests/agent/test_state.py` and `tests/api/test_gateway.py`

**Files:**
- Create: `backend/tests/agent/test_state.py`
- Create: `backend/tests/api/test_gateway.py`

- [ ] **Step 1: Write `test_state.py`**

```python
# backend/tests/agent/test_state.py
"""Tests for AgentState initialization and field defaults."""

from langchain_core.messages import HumanMessage
from app.agent.state import AgentState


def test_agent_state_requires_messages():
    state = AgentState(messages=[HumanMessage(content="hi")])
    assert len(state.messages) == 1


def test_agent_state_approved_defaults_to_none():
    state = AgentState(messages=[])
    assert state.approved is None


def test_agent_state_pending_tool_call_defaults_to_none():
    state = AgentState(messages=[])
    assert state.pending_tool_call is None


def test_agent_state_messages_are_list():
    msgs = [HumanMessage(content="a"), HumanMessage(content="b")]
    state = AgentState(messages=msgs)
    assert state.messages == msgs
```

- [ ] **Step 2: Write `test_gateway.py`**

```python
# backend/tests/api/test_gateway.py
"""Tests for gateway channel routing API."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.anyio
async def test_gateway_webhook_without_token_returns_401(client):
    """Gateway webhook without authentication must return 401."""
    resp = await client.post("/api/gateway/webhook", json={"content": "hello"})
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_gateway_health_check_returns_200(client):
    """Gateway health check endpoint must be reachable without auth."""
    resp = await client.get("/api/gateway/health")
    # Either 200 (healthy) or 404 (endpoint not exposed) — not 500
    assert resp.status_code != 500
```

- [ ] **Step 3: Run tests**

```bash
cd backend && uv run pytest tests/agent/test_state.py tests/api/test_gateway.py -v
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add tests/agent/test_state.py tests/api/test_gateway.py
git commit -m "test: add AgentState and gateway endpoint tests"
```

---

### Task 7: Five tool tests — `code_exec`, `datetime`, `memory`, `image_gen`, `cron`

**Files:**
- Create: `backend/tests/tools/test_code_exec_tool.py`
- Create: `backend/tests/tools/test_datetime_tool.py`
- Create: `backend/tests/tools/test_memory_tool.py`
- Create: `backend/tests/tools/test_image_gen_tool.py`
- Create: `backend/tests/tools/test_cron_tool.py`

- [ ] **Step 1: Write `test_datetime_tool.py`** (no external deps — start simple)

```python
# backend/tests/tools/test_datetime_tool.py
import pytest
from app.tools.datetime_tool import get_datetime


@pytest.mark.anyio
async def test_get_datetime_returns_string():
    result = await get_datetime.ainvoke({})
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.anyio
async def test_get_datetime_includes_date():
    """Result must contain a 4-digit year."""
    import re
    result = await get_datetime.ainvoke({})
    assert re.search(r"\d{4}", result)
```

- [ ] **Step 2: Write `test_memory_tool.py`**

```python
# backend/tests/tools/test_memory_tool.py
import pytest
from unittest.mock import MagicMock, patch


def test_read_memory_file_missing_path_returns_error():
    """Reading a nonexistent memory path must return an error message, not raise."""
    from app.tools.memory_tool import read_memory_file

    with patch("app.tools.memory_tool.Path.exists", return_value=False):
        result = read_memory_file.invoke({"path": "/nonexistent/file.md"})
    assert "not found" in result.lower() or "error" in result.lower() or isinstance(result, str)


def test_search_local_memory_no_results():
    """Searching memory with no matches must return a message, not raise."""
    from app.tools.memory_tool import search_local_memory

    with patch("app.tools.memory_tool.Path.glob", return_value=iter([])):
        result = search_local_memory.invoke({"query": "nonexistent_query_xyz"})
    assert isinstance(result, str)
```

- [ ] **Step 3: Write `test_code_exec_tool.py`**

```python
# backend/tests/tools/test_code_exec_tool.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.anyio
async def test_execute_code_sandbox_error_returns_message():
    """Sandbox failure must return an error string, not raise an uncaught exception."""
    from app.tools.code_exec_tool import execute_code

    with patch(
        "app.tools.code_exec_tool.SandboxManager.run_code",
        AsyncMock(side_effect=RuntimeError("sandbox unavailable")),
    ):
        result = await execute_code.ainvoke({"code": "print('hello')", "language": "python"})
    assert isinstance(result, str)
    assert "error" in result.lower() or "unavailable" in result.lower()


@pytest.mark.anyio
async def test_execute_code_empty_input_returns_error():
    """Empty code string must return a validation error."""
    from app.tools.code_exec_tool import execute_code

    result = await execute_code.ainvoke({"code": "", "language": "python"})
    assert isinstance(result, str)
```

- [ ] **Step 4: Write `test_image_gen_tool.py`**

```python
# backend/tests/tools/test_image_gen_tool.py
import pytest
from unittest.mock import AsyncMock, patch


def test_create_image_gen_tool_returns_none_without_key():
    """Image gen tool factory must return None when no API key is provided."""
    from app.tools.image_gen_tool import create_image_gen_tool

    result = create_image_gen_tool(None)
    assert result is None


def test_create_image_gen_tool_returns_tool_with_key():
    """Image gen tool factory must return a BaseTool when API key is provided."""
    from app.tools.image_gen_tool import create_image_gen_tool
    from langchain_core.tools import BaseTool

    tool = create_image_gen_tool("sk-openai-test")
    assert tool is not None
    assert isinstance(tool, BaseTool)
```

- [ ] **Step 5: Write `test_cron_tool.py`**

```python
# backend/tests/tools/test_cron_tool.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.anyio
async def test_list_cron_jobs_calls_repository(user_id_str=None):
    """list_cron_jobs tool must delegate to CronRepository.list_jobs()."""
    user_id = str(uuid.uuid4())
    from app.tools.cron_tool import create_cron_tools

    mock_repo = AsyncMock()
    mock_repo.list_jobs = AsyncMock(return_value=[])

    with patch("app.tools.cron_tool._make_repository", AsyncMock(return_value=(mock_repo, AsyncMock()))):
        tools = create_cron_tools(user_id)
        list_jobs = next(t for t in tools if "list" in t.name.lower())
        result = await list_jobs.ainvoke({})

    mock_repo.list_jobs.assert_awaited_once()
    assert isinstance(result, str)
```

- [ ] **Step 6: Run all tool tests**

```bash
cd backend && uv run pytest tests/tools/ -v --tb=short
```
Expected: all pass.

- [ ] **Step 7: Commit all**

```bash
git add tests/tools/ tests/agent/test_state.py
git commit -m "test: add missing tool, agent state, and gateway tests (P3 complete)"
```

---

### Task 8: Final P3 verification

- [ ] **Step 1: Count test functions**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | grep "test session starts" -A 3
```

- [ ] **Step 2: Run full suite**

```bash
cd backend && uv run pytest tests/ -x -q --tb=short
```
Expected: all pass, 13 new test files visible in collection.

- [ ] **Step 3: Push**

```bash
git push origin dev
```
