# Phase 6: Skills Platform + Voice + Canvas — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Evolve JARVIS from a chat platform into a fully extensible AI assistant with Skills-as-Markdown, MCP server connectivity, voice I/O, cron/webhook automation, usage insights, and Live Canvas.

**Architecture:** Incremental additions on top of the existing LangGraph + FastAPI stack. Skills are loaded at agent startup from Markdown files. MCP tools are bridged through the existing `_resolve_tools()` pattern. Voice is frontend-only (Web Speech API) plus optional backend TTS endpoint. Canvas uses an existing SSE channel with a new event type. Cron uses APScheduler persisted to DB.

**Tech Stack:** APScheduler, mcp Python SDK, edge-tts (free TTS), Web Speech API, APScheduler, Vue 3 SSE extensions

**Branch:** `feature/phase6-skills-voice-canvas` (from dev)

---

## Task 6.1: Skills-as-Markdown System

**Scope:** Agent reads `.md` files from `~/.jarvis/skills/` (or `backend/skills/`) and injects available skill descriptions into the system prompt. When a skill is referenced, the agent reads its full content.

**Files:**
- Create: `backend/app/agent/skills.py`
- Create: `backend/skills/example_skill.md`
- Modify: `backend/app/agent/persona.py` — inject skills listing into system prompt
- Modify: `backend/app/core/config.py` — add `SKILLS_DIR` setting
- Create: `backend/tests/agent/test_skills.py`

**Step 1: Write failing tests**

```python
# backend/tests/agent/test_skills.py
import tempfile, textwrap
from pathlib import Path
from app.agent.skills import load_skills, format_skills_for_prompt, SkillFile

def test_load_skills_from_directory():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "test_skill.md").write_text(textwrap.dedent("""
            ---
            name: test-skill
            description: A test skill for unit testing
            triggers:
              - run tests
              - execute tests
            ---
            # Test Skill
            When asked to run tests, execute: `pytest tests/ -v`
        """))
        skills = load_skills(d)
    assert len(skills) == 1
    assert skills[0].name == "test-skill"
    assert "A test skill" in skills[0].description

def test_load_skills_empty_directory():
    with tempfile.TemporaryDirectory() as d:
        skills = load_skills(d)
    assert skills == []

def test_load_skills_missing_directory():
    skills = load_skills("/nonexistent/path/skills")
    assert skills == []

def test_format_skills_for_prompt():
    skills = [
        SkillFile(name="git-helper", description="Help with git commands", triggers=["commit", "push"], content="..."),
        SkillFile(name="code-review", description="Review code quality", triggers=["review"], content="..."),
    ]
    result = format_skills_for_prompt(skills)
    assert "git-helper" in result
    assert "code-review" in result
    assert "commit" in result

def test_format_skills_for_prompt_empty():
    result = format_skills_for_prompt([])
    assert result == ""
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/agent/test_skills.py -v
```
Expected: ImportError (module doesn't exist yet)

**Step 3: Implement `backend/app/agent/skills.py`**

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class SkillFile:
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    content: str = ""


def load_skills(skills_dir: str | Path) -> list[SkillFile]:
    """Load all .md skill files from the given directory.

    Returns empty list if directory doesn't exist or has no valid skill files.
    """
    path = Path(skills_dir)
    if not path.is_dir():
        return []

    skills: list[SkillFile] = []
    for md_file in sorted(path.glob("*.md")):
        skill = _parse_skill_file(md_file)
        if skill is not None:
            skills.append(skill)
    logger.info("skills_loaded", count=len(skills), dir=str(path))
    return skills


def _parse_skill_file(md_file: Path) -> SkillFile | None:
    try:
        raw = md_file.read_text(encoding="utf-8")
    except OSError:
        logger.warning("skill_file_read_error", file=str(md_file))
        return None

    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return None

    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        logger.warning("skill_frontmatter_parse_error", file=str(md_file))
        return None

    name = meta.get("name") or md_file.stem
    description = meta.get("description", "")
    triggers = meta.get("triggers") or []

    return SkillFile(
        name=str(name),
        description=str(description),
        triggers=[str(t) for t in triggers],
        content=raw,
    )


def format_skills_for_prompt(skills: list[SkillFile]) -> str:
    """Format loaded skills as a block to append to the system prompt."""
    if not skills:
        return ""
    lines = ["", "## Available Skills", ""]
    for skill in skills:
        trigger_str = ", ".join(skill.triggers) if skill.triggers else "any relevant request"
        lines.append(f"- **{skill.name}**: {skill.description} (triggers: {trigger_str})")
    lines.append(
        "\nWhen a skill is relevant, follow its instructions precisely."
    )
    return "\n".join(lines)
```

**Step 4: Add `SKILLS_DIR` to config**

In `backend/app/core/config.py`, add to `Settings`:
```python
skills_dir: str = str(Path.home() / ".jarvis" / "skills")
```

**Step 5: Inject skills into persona**

In `backend/app/agent/persona.py`, modify `build_system_prompt()`:
```python
from app.agent.skills import load_skills, format_skills_for_prompt
from app.core.config import settings

def build_system_prompt(persona_override: str | None = None) -> str:
    base = persona_override or _DEFAULT_PERSONA
    skills = load_skills(settings.skills_dir)
    skills_block = format_skills_for_prompt(skills)
    return base + skills_block
```

**Step 6: Create example skill file**

Create `backend/skills/code-review.md`:
```markdown
---
name: code-review
description: Review Python code for bugs, style, and best practices
triggers:
  - review code
  - check code quality
  - code review
---
# Code Review Skill
When asked to review code:
1. Check for obvious bugs and logic errors
2. Verify error handling is appropriate
3. Check for security issues (injection, path traversal, etc.)
4. Suggest improvements without over-engineering
5. Be concise — highlight only significant issues
```

**Step 7: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/agent/test_skills.py -v
```
Expected: All PASS

**Step 8: Commit**

```bash
git add backend/app/agent/skills.py backend/app/agent/persona.py \
        backend/app/core/config.py backend/skills/ \
        backend/tests/agent/test_skills.py
git commit -m "feat: Skills-as-Markdown system with auto-injection into system prompt"
```

---

## Task 6.2: MCP Server Support (as MCP Client)

**Scope:** JARVIS connects to external MCP servers (stdio or HTTP). MCP-provided tools are auto-registered as LangGraph tools. Configuration via user_settings or server-level env var.

**Files:**
- Create: `backend/app/tools/mcp_client.py`
- Modify: `backend/app/agent/graph.py` — add MCP tools to `_resolve_tools()`
- Modify: `backend/app/core/config.py` — add `MCP_SERVERS` setting
- Modify: `backend/app/core/permissions.py` — add placeholder in registry
- Create: `backend/tests/tools/test_mcp_client.py`

**Step 1: Add mcp dependency**

```bash
cd backend && uv add mcp
```

**Step 2: Write failing tests**

```python
# backend/tests/tools/test_mcp_client.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.tools.mcp_client import create_mcp_tools, MCPServerConfig

def test_mcp_server_config_parse():
    config = MCPServerConfig(name="filesystem", command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"])
    assert config.name == "filesystem"
    assert config.command == "npx"

@pytest.mark.asyncio
async def test_create_mcp_tools_empty_config():
    tools = await create_mcp_tools([])
    assert tools == []

@pytest.mark.asyncio
async def test_create_mcp_tools_returns_callable_tools():
    mock_tool = MagicMock()
    mock_tool.name = "read_file"
    mock_tool.description = "Read a file"
    mock_tool.inputSchema = {"type": "object", "properties": {"path": {"type": "string"}}}

    mock_session = AsyncMock()
    mock_session.list_tools.return_value = MagicMock(tools=[mock_tool])
    mock_session.call_tool.return_value = MagicMock(content=[MagicMock(text="file contents")])

    with patch("app.tools.mcp_client._connect_mcp_server", return_value=mock_session):
        config = MCPServerConfig(name="test", command="echo", args=[])
        tools = await create_mcp_tools([config])

    assert len(tools) == 1
    assert tools[0].name == "read_file"
```

**Step 3: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/tools/test_mcp_client.py -v
```

**Step 4: Implement `backend/app/tools/mcp_client.py`**

```python
from __future__ import annotations

import json
from dataclasses import dataclass, field

import structlog
from langchain_core.tools import BaseTool, StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = structlog.get_logger(__name__)


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


async def _connect_mcp_server(config: MCPServerConfig) -> ClientSession:
    server_params = StdioServerParameters(
        command=config.command,
        args=config.args,
        env=config.env,
    )
    read, write = await stdio_client(server_params).__aenter__()
    session = ClientSession(read, write)
    await session.initialize()
    return session


async def create_mcp_tools(configs: list[MCPServerConfig]) -> list[BaseTool]:
    """Connect to MCP servers and return their tools as LangChain tools."""
    if not configs:
        return []

    tools: list[BaseTool] = []
    for config in configs:
        try:
            session = await _connect_mcp_server(config)
            result = await session.list_tools()
            for mcp_tool in result.tools:
                tools.append(_mcp_tool_to_langchain(mcp_tool, session))
            logger.info("mcp_tools_loaded", server=config.name, tool_count=len(result.tools))
        except Exception:
            logger.warning("mcp_server_connect_failed", server=config.name, exc_info=True)
    return tools


def _mcp_tool_to_langchain(mcp_tool: object, session: ClientSession) -> BaseTool:
    tool_name = mcp_tool.name  # type: ignore[attr-defined]
    tool_description = mcp_tool.description or tool_name  # type: ignore[attr-defined]

    async def _call(**kwargs: object) -> str:
        try:
            result = await session.call_tool(tool_name, arguments=kwargs)
            parts = [c.text for c in result.content if hasattr(c, "text")]
            return "\n".join(parts) or "(no output)"
        except Exception as e:
            return f"MCP tool error: {e}"

    return StructuredTool.from_function(
        coroutine=_call,
        name=tool_name,
        description=tool_description,
        args_schema=None,
    )
```

**Step 5: Add MCP config to settings**

In `backend/app/core/config.py`:
```python
import json
mcp_servers_json: str = ""  # JSON array of MCPServerConfig dicts, e.g. '[{"name":"fs","command":"npx","args":[...]}]'

@property
def mcp_server_configs(self) -> list[dict]:
    if not self.mcp_servers_json:
        return []
    try:
        return json.loads(self.mcp_servers_json)
    except (json.JSONDecodeError, ValueError):
        return []
```

**Step 6: Wire MCP tools into graph**

In `backend/app/agent/graph.py`, update `create_graph()` to accept and use MCP tools:
```python
# In _resolve_tools() or create_graph() signature, add:
async def _resolve_mcp_tools() -> list[BaseTool]:
    from app.tools.mcp_client import create_mcp_tools, MCPServerConfig
    configs = [MCPServerConfig(**c) for c in settings.mcp_server_configs]
    return await create_mcp_tools(configs)
```
Note: `create_graph` must become async or MCP tools must be pre-loaded. Prefer pre-loading at startup.

**Step 7: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/tools/test_mcp_client.py -v
```

**Step 8: Commit**

```bash
git add backend/app/tools/mcp_client.py backend/app/agent/graph.py \
        backend/app/core/config.py backend/tests/tools/test_mcp_client.py
git commit -m "feat: MCP server support — auto-register external MCP tools as LangGraph tools"
```

---

## Task 6.3: Cron Scheduling Tool

**Scope:** Agent can set, list, and delete cron jobs. Jobs are persisted to DB and executed by APScheduler. When triggered, jobs create new agent sessions.

**Files:**
- Create: `backend/app/tools/cron_tool.py`
- Create: `backend/app/scheduler/` (module)
- Create: `backend/app/scheduler/__init__.py`
- Create: `backend/app/scheduler/runner.py`
- Modify: `backend/app/db/models.py` — add `CronJob` model
- Create: `backend/alembic/versions/005_add_cron_jobs.py`
- Modify: `backend/app/main.py` — start/stop scheduler in lifespan
- Modify: `backend/app/agent/graph.py` — add cron tool to registry
- Modify: `backend/app/core/permissions.py` — register cron tool
- Create: `backend/tests/tools/test_cron_tool.py`

**Step 1: Add APScheduler dependency**

```bash
cd backend && uv add apscheduler
```

**Step 2: Add CronJob model to models.py**

```python
class CronJob(Base):
    __tablename__ = "cron_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    schedule: Mapped[str]  # cron expression e.g. "0 9 * * 1-5"
    task: Mapped[str]      # Natural language task description
    is_active: Mapped[bool] = mapped_column(default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

**Step 3: Create Alembic migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add_cron_jobs"
```
Review and apply:
```bash
uv run alembic upgrade head
```

**Step 4: Write failing tests**

```python
# backend/tests/tools/test_cron_tool.py
from unittest.mock import AsyncMock, patch
import pytest
from app.tools.cron_tool import create_cron_tools

@pytest.mark.asyncio
async def test_cron_set_creates_job():
    with patch("app.tools.cron_tool.AsyncSessionLocal") as mock_session_cls:
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_db.scalar.return_value = None

        cron_set, _, _ = create_cron_tools(user_id="test-user-id")
        result = await cron_set.ainvoke({"schedule": "0 9 * * 1-5", "task": "Send daily report"})

    assert "scheduled" in result.lower() or "created" in result.lower()

@pytest.mark.asyncio
async def test_cron_list_returns_jobs():
    from app.db.models import CronJob
    import uuid
    from datetime import datetime
    fake_job = CronJob(
        id=uuid.uuid4(),
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        schedule="0 9 * * 1-5",
        task="Daily report",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    with patch("app.tools.cron_tool.AsyncSessionLocal") as mock_session_cls:
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_db.scalars.return_value.all.return_value = [fake_job]

        _, cron_list, _ = create_cron_tools(user_id="00000000-0000-0000-0000-000000000001")
        result = await cron_list.ainvoke({})

    assert "Daily report" in result
    assert "0 9 * * 1-5" in result
```

**Step 5: Implement `backend/app/tools/cron_tool.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from langchain_core.tools import BaseTool, tool
from sqlalchemy import select

from app.db.models import CronJob
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)


def create_cron_tools(user_id: str) -> tuple[BaseTool, BaseTool, BaseTool]:
    uid = uuid.UUID(user_id)

    @tool
    async def cron_set(schedule: str, task: str) -> str:
        """Schedule a recurring task using a cron expression.

        Args:
            schedule: Cron expression (e.g. "0 9 * * 1-5" = weekdays at 9am)
            task: Natural language description of what to do when triggered
        """
        async with AsyncSessionLocal() as db:
            job = CronJob(user_id=uid, schedule=schedule, task=task)
            db.add(job)
            await db.commit()
            await db.refresh(job)
        logger.info("cron_job_created", user_id=user_id, job_id=str(job.id))
        return f"Scheduled: '{task}' with schedule '{schedule}' (id: {job.id})"

    @tool
    async def cron_list() -> str:
        """List all active cron jobs for the current user."""
        async with AsyncSessionLocal() as db:
            rows = await db.scalars(
                select(CronJob)
                .where(CronJob.user_id == uid, CronJob.is_active.is_(True))
                .order_by(CronJob.created_at)
            )
            jobs = rows.all()
        if not jobs:
            return "No active cron jobs."
        lines = ["Active cron jobs:"]
        for j in jobs:
            last = j.last_run_at.strftime("%Y-%m-%d %H:%M") if j.last_run_at else "never"
            lines.append(f"- [{j.id}] '{j.task}' | schedule: {j.schedule} | last run: {last}")
        return "\n".join(lines)

    @tool
    async def cron_delete(job_id: str) -> str:
        """Delete a cron job by its ID.

        Args:
            job_id: The UUID of the cron job to delete
        """
        try:
            jid = uuid.UUID(job_id)
        except ValueError:
            return f"Invalid job ID: {job_id}"
        async with AsyncSessionLocal() as db:
            job = await db.get(CronJob, jid)
            if job is None or job.user_id != uid:
                return f"Cron job {job_id} not found."
            job.is_active = False
            await db.commit()
        logger.info("cron_job_deleted", user_id=user_id, job_id=job_id)
        return f"Deleted cron job {job_id}."

    return cron_set, cron_list, cron_delete
```

**Step 6: Create scheduler runner**

Create `backend/app/scheduler/runner.py`:
```python
from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = structlog.get_logger(__name__)
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def start_scheduler() -> None:
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("scheduler_started")


async def stop_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
```

**Step 7: Wire scheduler into main.py lifespan**

```python
from app.scheduler.runner import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup code ...
    await start_scheduler()
    yield
    await stop_scheduler()
    # ... existing shutdown code ...
```

**Step 8: Register cron tool in permissions.py and graph.py**

In `permissions.py` TOOL_REGISTRY:
```python
"cron": ToolMeta(label="Cron Scheduler", description="Schedule recurring tasks", default_enabled=False),
```

In `graph.py` `_resolve_tools()`:
```python
if "cron" in enabled_tools and user_id:
    from app.tools.cron_tool import create_cron_tools
    cron_set, cron_list, cron_delete = create_cron_tools(user_id)
    tools.extend([cron_set, cron_list, cron_delete])
```

**Step 9: Run tests**

```bash
cd backend && uv run pytest tests/tools/test_cron_tool.py -v
```

**Step 10: Commit**

```bash
git add backend/app/tools/cron_tool.py backend/app/scheduler/ \
        backend/app/db/models.py backend/alembic/versions/005_add_cron_jobs.py \
        backend/app/main.py backend/app/agent/graph.py \
        backend/app/core/permissions.py backend/tests/tools/test_cron_tool.py
git commit -m "feat: Cron scheduling tool — agent can set/list/delete recurring tasks"
```

---

## Task 6.4: Webhook Trigger Endpoints

**Scope:** Users create named webhooks that trigger agent tasks when called. External services (GitHub, Zapier, etc.) call `POST /api/webhooks/{webhook_id}` to trigger JARVIS.

**Files:**
- Create: `backend/app/api/webhooks.py`
- Modify: `backend/app/db/models.py` — add `Webhook` model
- Create: `backend/alembic/versions/006_add_webhooks.py`
- Modify: `backend/app/main.py` — include webhooks router
- Create: `backend/tests/api/test_webhooks.py`

**Step 1: Add Webhook model to models.py**

```python
class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str]
    task_template: Mapped[str]  # e.g. "Process GitHub event: {payload}"
    secret_token: Mapped[str]   # HMAC verification token
    is_active: Mapped[bool] = mapped_column(default=True)
    trigger_count: Mapped[int] = mapped_column(default=0)
    last_triggered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

**Step 2: Create Alembic migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add_webhooks"
uv run alembic upgrade head
```

**Step 3: Write failing tests**

```python
# backend/tests/api/test_webhooks.py
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_create_webhook(auth_client: AsyncClient):
    resp = await auth_client.post("/api/webhooks", json={
        "name": "github-push",
        "task_template": "A GitHub push event occurred: {payload}"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "github-push"
    assert "id" in data
    assert "secret_token" in data

@pytest.mark.asyncio
async def test_trigger_webhook(client: AsyncClient, db_session):
    # First create a webhook
    webhook_id = "..."  # set up fixture
    secret = "test-secret"

    with patch("app.api.webhooks._trigger_agent_task", new_callable=AsyncMock):
        resp = await client.post(
            f"/api/webhooks/{webhook_id}/trigger",
            json={"event": "push", "repo": "JARVIS"},
            headers={"X-Webhook-Secret": secret},
        )
    assert resp.status_code == 202
```

**Step 4: Implement `backend/app/api/webhooks.py`**

```python
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, UTC

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import User, Webhook
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    name: str
    task_template: str


class WebhookResponse(BaseModel):
    id: uuid.UUID
    name: str
    task_template: str
    secret_token: str
    trigger_count: int
    is_active: bool
    created_at: datetime


@router.post("", status_code=201, response_model=WebhookResponse)
async def create_webhook(
    body: WebhookCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    webhook = Webhook(
        user_id=user.id,
        name=body.name,
        task_template=body.task_template,
        secret_token=secrets.token_urlsafe(32),
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return WebhookResponse(
        id=webhook.id,
        name=webhook.name,
        task_template=webhook.task_template,
        secret_token=webhook.secret_token,
        trigger_count=webhook.trigger_count,
        is_active=webhook.is_active,
        created_at=webhook.created_at,
    )


@router.post("/{webhook_id}/trigger", status_code=202)
async def trigger_webhook(
    webhook_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    webhook = await db.scalar(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.is_active.is_(True))
    )
    if webhook is None:
        raise HTTPException(status_code=404)

    # Verify HMAC secret if provided
    provided_secret = request.headers.get("X-Webhook-Secret", "")
    if not hmac.compare_digest(provided_secret, webhook.secret_token):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    payload_str = json.dumps(payload, ensure_ascii=False)[:2000]
    task = webhook.task_template.replace("{payload}", payload_str)

    webhook.trigger_count += 1
    webhook.last_triggered_at = datetime.now(UTC)
    await db.commit()

    # Fire-and-forget: trigger agent in background
    await _trigger_agent_task(webhook.user_id, task)

    logger.info("webhook_triggered", webhook_id=str(webhook_id), user_id=str(webhook.user_id))
    return {"status": "accepted", "task": task[:200]}


async def _trigger_agent_task(user_id: uuid.UUID, task: str) -> None:
    """Create a new conversation and run agent with the task."""
    # Imports here to avoid circular deps
    from app.gateway.models import GatewayMessage
    from app.gateway.router import GatewayRouter
    from app.gateway.channel_registry import ChannelRegistry
    from app.gateway.session_manager import SessionManager

    # This is a simplified fire-and-forget trigger
    # In production: push to a task queue (Redis/Celery)
    logger.info("webhook_agent_task_queued", user_id=str(user_id), task_preview=task[:100])
```

**Step 5: Register router in main.py**

```python
from app.api.webhooks import router as webhooks_router
app.include_router(webhooks_router)
```

**Step 6: Run tests**

```bash
cd backend && uv run pytest tests/api/test_webhooks.py -v
```

**Step 7: Commit**

```bash
git add backend/app/api/webhooks.py backend/app/db/models.py \
        backend/alembic/versions/006_add_webhooks.py \
        backend/app/main.py backend/tests/api/test_webhooks.py
git commit -m "feat: Webhook trigger endpoints — external events can activate JARVIS agent"
```

---

## Task 6.5: Usage Dashboard (Backend + Frontend)

**Scope:** Track token usage per LLM call and provide an API for aggregate stats. Frontend shows usage chart by day/model.

**Files (Backend):**
- Modify: `backend/app/api/chat.py` — capture token usage from LLM response
- Create: `backend/app/api/usage.py` — usage stats API
- Modify: `backend/app/main.py` — include usage router
- Create: `backend/tests/api/test_usage.py`

**Files (Frontend):**
- Create: `frontend/src/pages/UsagePage.vue`
- Modify: `frontend/src/router/index.ts` — add /usage route
- Modify: `frontend/src/api/index.ts` — add usage API calls

**Step 1: Note existing token fields**

`messages` table already has `tokens_input` and `tokens_output` columns. We just need to populate them and aggregate.

**Step 2: Populate token counts in chat.py**

In the `generate()` function's finally block when saving AI message, extract token usage from LangGraph stream chunks:
```python
# Track token usage from LLM response metadata
tokens_in = 0
tokens_out = 0
# LangChain AIMessage has .usage_metadata: {"input_tokens": N, "output_tokens": N}
if hasattr(last_ai_msg, "usage_metadata") and last_ai_msg.usage_metadata:
    tokens_in = last_ai_msg.usage_metadata.get("input_tokens", 0)
    tokens_out = last_ai_msg.usage_metadata.get("output_tokens", 0)
```

**Step 3: Create usage API**

```python
# backend/app/api/usage.py
from datetime import date, timedelta
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import Message, Conversation, User

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/summary")
async def get_usage_summary(
    days: int = 30,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return daily token usage for the past N days."""
    since = date.today() - timedelta(days=days)
    rows = await db.execute(
        select(
            func.date(Message.created_at).label("day"),
            Message.model_provider,
            func.sum(Message.tokens_input).label("tokens_in"),
            func.sum(Message.tokens_output).label("tokens_out"),
            func.count().label("messages"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == user.id,
            Message.role == "ai",
            Message.created_at >= since,
        )
        .group_by(func.date(Message.created_at), Message.model_provider)
        .order_by(func.date(Message.created_at))
    )
    data = [
        {"day": str(r.day), "provider": r.model_provider, "tokens_in": r.tokens_in or 0,
         "tokens_out": r.tokens_out or 0, "messages": r.messages}
        for r in rows.all()
    ]
    total_in = sum(d["tokens_in"] for d in data)
    total_out = sum(d["tokens_out"] for d in data)
    return {"daily": data, "total_tokens_in": total_in, "total_tokens_out": total_out}
```

**Step 4: Create UsagePage.vue frontend component**

```vue
<!-- frontend/src/pages/UsagePage.vue -->
<template>
  <div class="usage-page">
    <h1>{{ t('usage.title') }}</h1>

    <div class="stats-summary">
      <div class="stat-card">
        <div class="stat-value">{{ totalTokensIn.toLocaleString() }}</div>
        <div class="stat-label">{{ t('usage.tokensIn') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ totalTokensOut.toLocaleString() }}</div>
        <div class="stat-label">{{ t('usage.tokensOut') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ totalMessages }}</div>
        <div class="stat-label">{{ t('usage.messages') }}</div>
      </div>
    </div>

    <!-- Simple bar chart using CSS -->
    <div class="chart-container">
      <div v-for="day in dailyData" :key="day.day" class="chart-bar-group">
        <div
          class="chart-bar"
          :style="{ height: barHeight(day.tokens_out) + 'px' }"
          :title="`${day.day}: ${day.tokens_out} tokens out`"
        />
        <div class="chart-label">{{ formatDay(day.day) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getUsageSummary } from '@/api'

const { t } = useI18n()
const dailyData = ref<Array<{day: string, tokens_in: number, tokens_out: number, messages: number, provider: string}>>([])
const totalTokensIn = ref(0)
const totalTokensOut = ref(0)
const totalMessages = computed(() => dailyData.value.reduce((s, d) => s + d.messages, 0))
const maxTokens = computed(() => Math.max(...dailyData.value.map(d => d.tokens_out), 1))

const barHeight = (tokens: number) => Math.round((tokens / maxTokens.value) * 120)
const formatDay = (day: string) => day.slice(5)  // MM-DD

onMounted(async () => {
  const data = await getUsageSummary(30)
  dailyData.value = data.daily
  totalTokensIn.value = data.total_tokens_in
  totalTokensOut.value = data.total_tokens_out
})
</script>
```

**Step 5: Add usage route and navigation link**

In `frontend/src/router/index.ts`:
```typescript
{ path: '/usage', component: () => import('@/pages/UsagePage.vue'), meta: { requiresAuth: true } }
```

**Step 6: Add API function**

In `frontend/src/api/index.ts`:
```typescript
export const getUsageSummary = (days = 30) =>
  axios.get(`/api/usage/summary?days=${days}`).then(r => r.data)
```

**Step 7: Run backend tests**

```bash
cd backend && uv run pytest tests/api/test_usage.py -v
```

**Step 8: Commit**

```bash
git add backend/app/api/usage.py backend/app/api/chat.py backend/app/main.py \
        backend/tests/api/test_usage.py \
        frontend/src/pages/UsagePage.vue frontend/src/router/index.ts \
        frontend/src/api/index.ts
git commit -m "feat: Usage dashboard — token tracking API and frontend chart"
```

---

## Task 6.6: TTS Voice Reply

**Scope:** Backend TTS endpoint using edge-tts (free, Microsoft neural voices). Frontend plays audio inline in chat messages.

**Files:**
- Create: `backend/app/api/tts.py`
- Modify: `backend/app/core/config.py` — add TTS settings
- Modify: `backend/app/main.py` — include TTS router
- Modify: `frontend/src/pages/ChatPage.vue` — add TTS playback button
- Create: `backend/tests/api/test_tts.py`

**Step 1: Add edge-tts dependency**

```bash
cd backend && uv add edge-tts
```

**Step 2: Write failing tests**

```python
# backend/tests/api/test_tts.py
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_tts_synthesize(auth_client: AsyncClient):
    with patch("app.api.tts.edge_tts.Communicate") as mock_comm:
        mock_instance = AsyncMock()
        mock_instance.stream.return_value = [
            (b"audio-data-1", {"type": "audio"}),
        ].__aiter__()
        mock_comm.return_value = mock_instance

        resp = await auth_client.post("/api/tts/synthesize", json={
            "text": "Hello world",
            "voice": "en-US-JennyNeural"
        })

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"

@pytest.mark.asyncio
async def test_tts_empty_text(auth_client: AsyncClient):
    resp = await auth_client.post("/api/tts/synthesize", json={"text": ""})
    assert resp.status_code == 422
```

**Step 3: Implement `backend/app/api/tts.py`**

```python
from __future__ import annotations

import io
from collections.abc import AsyncGenerator

import edge_tts
import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.db.models import User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/tts", tags=["tts"])

_DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"  # Friendly Chinese voice
_VOICES = {
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-JennyNeural",
    "ja": "ja-JP-NanamiNeural",
}


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice: str = _DEFAULT_VOICE
    rate: str = "+0%"  # e.g. "+10%", "-20%"


@router.post("/synthesize")
async def synthesize(
    body: TTSRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    async def _stream() -> AsyncGenerator[bytes, None]:
        communicate = edge_tts.Communicate(body.text, body.voice, rate=body.rate)
        async for chunk, _ in communicate.stream():
            if chunk:
                yield chunk

    logger.info("tts_synthesize", user_id=str(user.id), voice=body.voice, chars=len(body.text))
    return StreamingResponse(_stream(), media_type="audio/mpeg")


@router.get("/voices")
async def list_voices(user: User = Depends(get_current_user)) -> dict:
    return {"voices": list(_VOICES.values()), "default": _DEFAULT_VOICE}
```

**Step 4: Add TTS button to ChatPage.vue**

In each AI message bubble, add a speaker icon button that:
1. Calls `POST /api/tts/synthesize` with the message content
2. Creates an `Audio` object from the blob response
3. Plays it inline

```typescript
// In chat store or component
const playTTS = async (text: string) => {
  const resp = await fetch('/api/tts/synthesize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ text, voice: 'zh-CN-XiaoxiaoNeural' })
  })
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  audio.play()
  audio.onended = () => URL.revokeObjectURL(url)
}
```

**Step 5: Run tests**

```bash
cd backend && uv run pytest tests/api/test_tts.py -v
```

**Step 6: Commit**

```bash
git add backend/app/api/tts.py backend/app/main.py \
        backend/tests/api/test_tts.py \
        frontend/src/pages/ChatPage.vue
git commit -m "feat: TTS voice reply — edge-tts backend with frontend audio playback"
```

---

## Task 6.7: Voice Input (Web Speech API)

**Scope:** Frontend-only. Add a microphone button to the chat input that uses the Web Speech API for speech-to-text. No backend changes needed.

**Files:**
- Modify: `frontend/src/pages/ChatPage.vue` — add mic button and speech recognition
- Create: `frontend/src/composables/useSpeechInput.ts`

**Step 1: Create voice input composable**

```typescript
// frontend/src/composables/useSpeechInput.ts
import { ref } from 'vue'

export function useSpeechInput(onResult: (text: string) => void) {
  const isListening = ref(false)
  const isSupported = 'SpeechRecognition' in window || 'webkitSpeechRecognition' in window

  let recognition: SpeechRecognition | null = null

  const start = () => {
    if (!isSupported) return

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    recognition = new SpeechRecognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = navigator.language || 'zh-CN'

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript
      onResult(transcript)
      isListening.value = false
    }

    recognition.onerror = () => { isListening.value = false }
    recognition.onend = () => { isListening.value = false }

    recognition.start()
    isListening.value = true
  }

  const stop = () => {
    recognition?.stop()
    isListening.value = false
  }

  return { isListening, isSupported, start, stop }
}
```

**Step 2: Add mic button to ChatPage.vue**

In the chat input area, add:
```vue
<button
  v-if="speechInput.isSupported"
  @click="speechInput.isListening.value ? speechInput.stop() : speechInput.start()"
  :class="{ active: speechInput.isListening.value }"
  class="mic-button"
  :title="speechInput.isListening.value ? t('chat.stopListening') : t('chat.startVoice')"
>
  🎤
</button>
```

Wire it up:
```typescript
const inputText = ref('')
const speechInput = useSpeechInput((text) => { inputText.value += text })
```

**Step 3: Commit**

```bash
git add frontend/src/composables/useSpeechInput.ts \
        frontend/src/pages/ChatPage.vue
git commit -m "feat: Voice input — Web Speech API mic button in chat"
```

---

## Task 6.8: Live Canvas

**Scope:** Agent can push HTML/CSS/JS to a frontend Canvas panel via SSE. A new `canvas_render` tool lets the agent create interactive visualizations.

**Files:**
- Create: `backend/app/tools/canvas_tool.py`
- Create: `backend/app/api/canvas.py` — SSE endpoint for canvas events
- Modify: `backend/app/main.py` — include canvas router
- Modify: `backend/app/core/permissions.py` — register canvas tool
- Modify: `backend/app/agent/graph.py` — add canvas tool
- Create: `frontend/src/components/CanvasPanel.vue`
- Modify: `frontend/src/pages/ChatPage.vue` — add canvas panel toggle
- Create: `backend/tests/tools/test_canvas_tool.py`

**Step 1: Write failing tests**

```python
# backend/tests/tools/test_canvas_tool.py
import pytest
from app.tools.canvas_tool import create_canvas_tool, CanvasEventBus

@pytest.mark.asyncio
async def test_canvas_render_emits_event():
    bus = CanvasEventBus()
    canvas_render = create_canvas_tool(conversation_id="test-conv-id", event_bus=bus)

    events = []
    async def collect():
        async for ev in bus.subscribe("test-conv-id"):
            events.append(ev)
            break

    import asyncio
    collector = asyncio.create_task(collect())
    await asyncio.sleep(0.01)

    result = await canvas_render.ainvoke({"html": "<h1>Hello Canvas</h1>", "title": "Test"})
    await asyncio.sleep(0.01)
    collector.cancel()

    assert "rendered" in result.lower() or "canvas" in result.lower()
```

**Step 2: Implement `backend/app/tools/canvas_tool.py`**

```python
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

import structlog
from langchain_core.tools import BaseTool, tool

logger = structlog.get_logger(__name__)


class CanvasEventBus:
    """In-process pub/sub for canvas events per conversation."""

    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, conversation_id: str, event: dict[str, Any]) -> None:
        for q in list(self._queues[conversation_id]):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def subscribe(self, conversation_id: str):
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._queues[conversation_id].append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._queues[conversation_id].remove(q)


# Module-level singleton
_canvas_bus = CanvasEventBus()


def get_canvas_bus() -> CanvasEventBus:
    return _canvas_bus


def create_canvas_tool(
    conversation_id: str,
    event_bus: CanvasEventBus | None = None,
) -> BaseTool:
    bus = event_bus or _canvas_bus

    @tool
    async def canvas_render(html: str, title: str = "Canvas") -> str:
        """Render HTML content in the frontend Canvas panel.

        Args:
            html: HTML/CSS/JS content to display (sandboxed iframe)
            title: Optional title for the canvas panel
        """
        await bus.publish(conversation_id, {
            "type": "canvas_render",
            "title": title,
            "html": html,
        })
        logger.info("canvas_rendered", conv_id=conversation_id, title=title)
        return f"Canvas rendered: '{title}' ({len(html)} chars)"

    return canvas_render
```

**Step 3: Create SSE canvas endpoint**

```python
# backend/app/api/canvas.py
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.db.models import User
from app.tools.canvas_tool import get_canvas_bus

router = APIRouter(prefix="/api/canvas", tags=["canvas"])


@router.get("/stream/{conversation_id}")
async def canvas_stream(
    conversation_id: str,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    async def _generate() -> AsyncGenerator[str, None]:
        bus = get_canvas_bus()
        async for event in bus.subscribe(conversation_id):
            yield "data: " + json.dumps(event) + "\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")
```

**Step 4: Create CanvasPanel.vue**

```vue
<!-- frontend/src/components/CanvasPanel.vue -->
<template>
  <div class="canvas-panel" v-if="isOpen">
    <div class="canvas-header">
      <span>{{ currentTitle || 'Canvas' }}</span>
      <button @click="isOpen = false">✕</button>
    </div>
    <iframe
      class="canvas-frame"
      sandbox="allow-scripts allow-same-origin"
      :srcdoc="currentHtml"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps<{ conversationId: string }>()
const isOpen = ref(false)
const currentHtml = ref('')
const currentTitle = ref('')
let eventSource: EventSource | null = null

onMounted(() => {
  const token = localStorage.getItem('token')
  eventSource = new EventSource(`/api/canvas/stream/${props.conversationId}?token=${token}`)
  eventSource.onmessage = (e) => {
    const event = JSON.parse(e.data)
    if (event.type === 'canvas_render') {
      currentHtml.value = event.html
      currentTitle.value = event.title
      isOpen.value = true
    }
  }
})

onUnmounted(() => { eventSource?.close() })

defineExpose({ isOpen })
</script>
```

**Step 5: Run tests**

```bash
cd backend && uv run pytest tests/tools/test_canvas_tool.py -v
```

**Step 6: Commit**

```bash
git add backend/app/tools/canvas_tool.py backend/app/api/canvas.py \
        backend/app/main.py backend/app/agent/graph.py \
        backend/app/core/permissions.py \
        frontend/src/components/CanvasPanel.vue \
        frontend/src/pages/ChatPage.vue \
        backend/tests/tools/test_canvas_tool.py
git commit -m "feat: Live Canvas — agent can push HTML visualizations to frontend panel"
```

---

## Task 6.9: PWA Mobile Support

**Scope:** Add PWA manifest and service worker to the frontend for installability on mobile devices. Minimum viable PWA — no complex offline support.

**Files:**
- Create: `frontend/public/manifest.json`
- Create: `frontend/public/sw.js` (minimal service worker)
- Modify: `frontend/index.html` — add PWA meta tags and manifest link
- Modify: `frontend/vite.config.ts` — no changes needed (Vite handles static assets)

**Step 1: Create `frontend/public/manifest.json`**

```json
{
  "name": "JARVIS AI Assistant",
  "short_name": "JARVIS",
  "description": "Your personal AI assistant",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1a1a2e",
  "theme_color": "#4f46e5",
  "orientation": "portrait",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

**Step 2: Create minimal service worker `frontend/public/sw.js`**

```javascript
// Minimal service worker — just enables PWA installability
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', () => self.clients.claim())
// Network-first strategy (no offline caching for now)
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request))
})
```

**Step 3: Add to `frontend/index.html`**

```html
<link rel="manifest" href="/manifest.json" />
<meta name="theme-color" content="#4f46e5" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<script>
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js')
  }
</script>
```

**Step 4: Add icons** (use placeholder 192×192 and 512×512 PNG files)

**Step 5: Commit**

```bash
git add frontend/public/manifest.json frontend/public/sw.js \
        frontend/index.html frontend/public/icon-192.png frontend/public/icon-512.png
git commit -m "feat: PWA support — installable on mobile with manifest and service worker"
```

---

## Execution Order

| Order | Task | Dependencies | Estimated Complexity |
|-------|------|-------------|---------------------|
| 1 | 6.1 Skills-as-Markdown | None | Low |
| 2 | 6.2 MCP Server Support | None | Medium |
| 3 | 6.3 Cron Scheduling | None | Medium |
| 4 | 6.4 Webhook Triggers | 6.3 (models pattern) | Low-Medium |
| 5 | 6.5 Usage Dashboard | None | Low-Medium |
| 6 | 6.6 TTS Voice Reply | None | Low |
| 7 | 6.7 Voice Input | None | Low (frontend only) |
| 8 | 6.8 Live Canvas | None | Medium |
| 9 | 6.9 PWA Support | None | Low |

Tasks 6.1–6.9 are largely independent. Run in order to minimize DB migration conflicts (6.3 must precede 6.4 as both add DB tables — apply migrations in order).

---

## Verification

```bash
# Backend quality
cd backend
uv run ruff check --fix && uv run ruff format
uv run mypy app
uv run pytest tests/ -v

# Frontend quality
cd frontend
bun run lint:fix && bun run type-check

# Full stack
pre-commit run --all-files
```
