# Proactive Monitoring V2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the proactive monitoring feature to fix 20 deficiencies: replace in-process APScheduler execution with ARQ worker queue, add execution history, improve content extraction, fix trigger processors, and enhance frontend UX.

**Architecture:** APScheduler enqueues job IDs to Redis via ARQ; a separate ARQ worker process consumes and executes trigger evaluation + agent invocation, writing results to a new `job_executions` table. All trigger processors return a `TriggerResult` dataclass (replacing raw `bool`) so change context flows into the agent task prompt.

**Tech Stack:** ARQ (async Redis task queue), trafilatura (already installed, content extraction), Pydantic structured output (LLM JSON responses), FastAPI, SQLAlchemy async, Vue 3 + TypeScript.

**Spec:** `docs/superpowers/specs/2026-03-12-proactive-monitoring-v2-design.md`

---

## Chunk 1: Foundation — TriggerResult, DB Model, Config

### Task 1: TriggerResult dataclass

**Files:**
- Create: `backend/app/scheduler/trigger_result.py`
- Test: `backend/tests/scheduler/test_trigger_result.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/scheduler/test_trigger_result.py
from app.scheduler.trigger_result import TriggerResult


def test_trigger_result_fired():
    r = TriggerResult(fired=True, reason="fired", trigger_ctx={"url": "x"})
    assert r.fired is True
    assert r.reason == "fired"
    assert r.trigger_ctx == {"url": "x"}


def test_trigger_result_skipped_defaults():
    r = TriggerResult(fired=False, reason="content_hash_unchanged")
    assert r.fired is False
    assert r.trigger_ctx is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/scheduler/test_trigger_result.py -v
```
Expected: `ModuleNotFoundError` — `trigger_result` does not exist yet.

- [ ] **Step 3: Implement**

```python
# backend/app/scheduler/trigger_result.py
from dataclasses import dataclass, field


@dataclass
class TriggerResult:
    fired: bool
    reason: str  # fired | skipped | content_hash_unchanged | no_new_emails | llm_parse_error | error
    trigger_ctx: dict | None = field(default=None)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/scheduler/test_trigger_result.py -v
```
Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/scheduler/trigger_result.py backend/tests/scheduler/test_trigger_result.py
git commit -m "feat(monitoring): add TriggerResult dataclass"
```

---

### Task 2: JobExecution DB model + Alembic migration

**Files:**
- Modify: `backend/app/db/models.py` — add `JobExecution` model, update `CronJob`
- Create: `backend/alembic/versions/012_add_job_executions.py`
- Test: `backend/tests/test_job_execution_model.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_job_execution_model.py
"""Smoke test: verify JobExecution model imports and has expected columns."""
from app.db.models import JobExecution, CronJob


def test_job_execution_columns():
    cols = {c.key for c in JobExecution.__table__.columns}
    assert "id" in cols
    assert "job_id" in cols
    assert "fired_at" in cols
    assert "status" in cols
    assert "trigger_ctx" in cols
    assert "agent_result" in cols
    assert "duration_ms" in cols
    assert "error_msg" in cols
    assert "attempt" in cols
    assert "run_group_id" in cols


def test_cron_job_has_executions_relationship():
    assert hasattr(CronJob, "executions")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_job_execution_model.py -v
```
Expected: `ImportError` — `JobExecution` not in models.

- [ ] **Step 3: Add model to `models.py`**

Open `backend/app/db/models.py`. After the `CronJob` class, add:

```python
class JobExecution(Base):
    __tablename__ = "job_executions"

    id: Mapped[uuid_pkg.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_pkg.uuid4
    )
    job_id: Mapped[uuid_pkg.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cron_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_group_id: Mapped[uuid_pkg.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # fired | skipped | error
    trigger_ctx: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    agent_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")

    job: Mapped["CronJob"] = relationship("CronJob", back_populates="executions")
```

In the `CronJob` class, add after `created_at`:

```python
    executions: Mapped[list["JobExecution"]] = relationship(
        "JobExecution", back_populates="job", cascade="all, delete-orphan"
    )
```

Add `SmallInteger` to the SQLAlchemy import at the top of `models.py`. The current import line looks like:

```python
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
```

Update it to:

```python
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
```

(`Integer`, `Text`, and `func` are already present; only `SmallInteger` needs to be added.)

- [ ] **Step 4: Create migration**

```python
# backend/alembic/versions/012_add_job_executions.py
"""add job_executions table

Revision ID: 012
Revises: 011
Create Date: 2026-03-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_executions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cron_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_group_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "fired_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("trigger_ctx", JSONB, nullable=True),
        sa.Column("agent_result", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("attempt", sa.SmallInteger, server_default="1", nullable=False),
    )
    op.create_index("idx_job_executions_job_id", "job_executions", ["job_id"])
    op.create_index(
        "idx_job_executions_fired_at",
        "job_executions",
        ["fired_at"],
        postgresql_ops={"fired_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_job_executions_fired_at", table_name="job_executions")
    op.drop_index("idx_job_executions_job_id", table_name="job_executions")
    op.drop_table("job_executions")
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_job_execution_model.py -v
```
Expected: 2 PASSED.

- [ ] **Step 6: Verify collect-only (import check)**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add backend/app/db/models.py \
        backend/alembic/versions/012_add_job_executions.py \
        backend/tests/test_job_execution_model.py
git commit -m "feat(monitoring): add JobExecution model and migration 012"
```

---

### Task 3: Config — MAX_CRON_JOBS_PER_USER

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Add setting**

Open `backend/app/core/config.py`. In the `Settings` class, add after the last non-sensitive setting:

```python
    max_cron_jobs_per_user: int = 20
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from app.core.config import settings; print(settings.max_cron_jobs_per_user)"
```
Expected: `20`

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/config.py
git commit -m "feat(monitoring): add MAX_CRON_JOBS_PER_USER config setting"
```

---

## Chunk 2: Content Fetching Helpers

### Task 4: URL validation (SSRF protection)

**Files:**
- Create: `backend/app/scheduler/fetch.py`
- Test: `backend/tests/scheduler/test_fetch.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/scheduler/test_fetch.py
import pytest

from app.scheduler.fetch import sanitize_http_headers, validate_fetch_url


# --- validate_fetch_url ---

def test_valid_public_url():
    validate_fetch_url("https://example.com/page")  # must not raise


def test_blocks_loopback():
    with pytest.raises(ValueError, match="blocked"):
        validate_fetch_url("http://127.0.0.1/admin")


def test_blocks_private_10():
    with pytest.raises(ValueError, match="blocked"):
        validate_fetch_url("http://10.0.0.1/secret")


def test_blocks_private_192():
    with pytest.raises(ValueError, match="blocked"):
        validate_fetch_url("http://192.168.1.1/")


def test_blocks_link_local():
    with pytest.raises(ValueError, match="blocked"):
        validate_fetch_url("http://169.254.169.254/latest/meta-data/")


def test_blocks_non_http_scheme():
    with pytest.raises(ValueError, match="scheme"):
        validate_fetch_url("ftp://example.com/file")


# --- sanitize_http_headers ---

def test_strips_host_header():
    result = sanitize_http_headers({"Host": "evil.com", "Authorization": "Bearer x"})
    assert "Host" not in result
    assert result.get("Authorization") == "Bearer x"


def test_strips_forwarded_headers():
    headers = {
        "X-Forwarded-For": "1.2.3.4",
        "X-Forwarded-Host": "evil.com",
        "X-Real-IP": "1.2.3.4",
        "Cookie": "session=abc",
    }
    result = sanitize_http_headers(headers)
    assert "X-Forwarded-For" not in result
    assert "X-Forwarded-Host" not in result
    assert "X-Real-IP" not in result
    assert result["Cookie"] == "session=abc"


def test_empty_headers():
    assert sanitize_http_headers({}) == {}
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/scheduler/test_fetch.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# backend/app/scheduler/fetch.py
"""Content fetching helpers: URL validation (SSRF protection) and header sanitization."""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx
import trafilatura

_HEADER_BLOCKLIST = frozenset(
    {
        "host",
        "x-forwarded-for",
        "x-forwarded-host",
        "x-forwarded-proto",
        "x-real-ip",
        "x-original-url",
        "x-rewrite-url",
    }
)

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_fetch_url(url: str) -> None:
    """Raise ValueError if URL points to a private/loopback/link-local address or non-HTTP scheme."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme '{parsed.scheme}' not allowed; only http/https")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    try:
        resolved_ip = socket.getaddrinfo(hostname, None)[0][4][0]
        addr = ipaddress.ip_address(resolved_ip)
    except (socket.gaierror, ValueError) as exc:
        raise ValueError(f"Cannot resolve hostname '{hostname}': {exc}") from exc

    for network in _PRIVATE_NETWORKS:
        if addr in network:
            raise ValueError(
                f"URL resolves to blocked address {addr} in network {network}"
            )


def sanitize_http_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove hop-by-hop and routing headers that could be abused for SSRF."""
    return {k: v for k, v in headers.items() if k.lower() not in _HEADER_BLOCKLIST}


async def fetch_page_content(
    url: str,
    http_headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    max_chars: int = 8000,
) -> str:
    """
    Fetch URL and extract main text content via trafilatura.

    Raises ValueError if URL is blocked by SSRF policy.
    Returns empty string if extraction fails (safe fallback).
    """
    validate_fetch_url(url)
    safe_headers = sanitize_http_headers(http_headers or {})

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = await client.get(url, headers=safe_headers)
        response.raise_for_status()
        html = response.text

    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
    )
    text = extracted or ""
    return text[:max_chars]
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/scheduler/test_fetch.py -v
```
Expected: all PASSED. (Note: `test_blocks_link_local` may fail in some CI environments if DNS resolves differently — if so, mock `socket.getaddrinfo`.)

- [ ] **Step 5: Lint and type-check**

```bash
cd backend && uv run ruff check --fix app/scheduler/fetch.py && uv run ruff format app/scheduler/fetch.py
cd backend && uv run mypy app/scheduler/fetch.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/scheduler/fetch.py backend/tests/scheduler/test_fetch.py
git commit -m "feat(monitoring): add URL validation and page content fetcher"
```

---

## Chunk 3: Trigger Processor Refactor

### Task 5: SemanticWatcher refactor

**Files:**
- Modify: `backend/app/scheduler/triggers.py`
- Modify: `backend/app/scheduler/prompts.py`
- Modify: `backend/tests/scheduler/test_semantic_watcher.py`

The key changes:
1. `evaluate_trigger()` and all processors return `TriggerResult` instead of `bool`
2. SemanticWatcher: content hash pre-check → skip LLM if unchanged
3. SemanticWatcher: structured JSON output via `with_structured_output`
4. SemanticWatcher: first-run logic handled in Python, not in prompt
5. Prompt: remove "rule #3" (first-run instruction)

- [ ] **Step 1: Update the prompt in `prompts.py`**

Replace the current `SEMANTIC_WATCHER_SYSTEM_PROMPT` and `SEMANTIC_WATCHER_USER_PROMPT` with:

```python
# backend/app/scheduler/prompts.py
SEMANTIC_WATCHER_SYSTEM_PROMPT = """\
你是一个专业的网页语义分析专家，擅长识别内容中的实质性变动并排除干扰信息。
你必须以 JSON 格式回复，包含三个字段：
- changed (bool): 是否检测到符合监控目标的语义变动
- summary (str): 简短描述变动内容（changed=true 时）或未变化原因（changed=false 时）
- confidence (str): "high" | "medium" | "low"
"""

SEMANTIC_WATCHER_USER_PROMPT = """\
当前监控目标：{target}
旧的内容摘要：{last_summary}
最新网页正文内容：
{new_content}

请分析：相对于旧的摘要，最新内容是否发生了符合监控目标的实质性语义变动？
排除无关紧要的变动（格式调整、广告更换、时间戳更新等）。
"""
```

- [ ] **Step 2: Write updated tests**

```python
# backend/tests/scheduler/test_semantic_watcher.py
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scheduler.trigger_result import TriggerResult
from app.scheduler.triggers import SemanticWatcherProcessor


@pytest.fixture()
def processor():
    return SemanticWatcherProcessor()


@pytest.mark.asyncio
async def test_first_run_fire_on_init_false(processor):
    """First run with fire_on_init=False: initializes state, does NOT fire."""
    metadata = {
        "url": "https://example.com",
        "target": "产品价格",
        "fire_on_init": False,
    }
    with patch("app.scheduler.triggers.fetch_page_content", new=AsyncMock(return_value="Price: $99")):
        result = await processor.should_fire(metadata)
    assert isinstance(result, TriggerResult)
    assert result.fired is False
    assert result.reason == "first_run_initialized"
    assert "content_hash" in metadata
    assert metadata["last_semantic_summary"] == "Price: $99"[:200]


@pytest.mark.asyncio
async def test_first_run_fire_on_init_true(processor):
    """First run with fire_on_init=True: fires immediately."""
    metadata = {
        "url": "https://example.com",
        "target": "产品价格",
        "fire_on_init": True,
    }
    with patch("app.scheduler.triggers.fetch_page_content", new=AsyncMock(return_value="Price: $99")):
        result = await processor.should_fire(metadata)
    assert result.fired is True
    assert result.reason == "fired"
    assert result.trigger_ctx is not None
    assert result.trigger_ctx["changed_summary"] == "已初始化监控"


@pytest.mark.asyncio
async def test_content_hash_unchanged_skips_llm(processor):
    """If content hash matches, LLM is NOT called."""
    content = "Price: $99"
    content_hash = hashlib.md5(content.encode()).hexdigest()
    metadata = {
        "url": "https://example.com",
        "target": "产品价格",
        "content_hash": content_hash,
        "last_semantic_summary": "价格为 $99",
    }
    with patch("app.scheduler.triggers.fetch_page_content", new=AsyncMock(return_value=content)):
        with patch("app.scheduler.triggers.get_llm_with_fallback") as mock_llm:
            result = await processor.should_fire(metadata)
    mock_llm.assert_not_called()
    assert result.fired is False
    assert result.reason == "content_hash_unchanged"


@pytest.mark.asyncio
async def test_semantic_change_detected(processor):
    """Content changed + LLM says changed=True → fires."""
    old_content = "Price: $99"
    new_content = "Price: $49"
    old_hash = hashlib.md5(old_content.encode()).hexdigest()
    metadata = {
        "url": "https://example.com",
        "target": "产品价格",
        "content_hash": old_hash,
        "last_semantic_summary": "价格为 $99",
    }

    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(
        return_value=MagicMock(changed=True, summary="价格从 $99 降至 $49", confidence="high")
    )
    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    with patch("app.scheduler.triggers.fetch_page_content", new=AsyncMock(return_value=new_content)):
        with patch("app.scheduler.triggers.get_llm_with_fallback", return_value=mock_llm):
            result = await processor.should_fire(metadata)

    assert result.fired is True
    assert result.reason == "fired"
    assert result.trigger_ctx["changed_summary"] == "价格从 $99 降至 $49"
    assert result.trigger_ctx["confidence"] == "high"
    assert metadata["last_semantic_summary"] == "价格从 $99 降至 $49"


@pytest.mark.asyncio
async def test_semantic_no_change(processor):
    """Content changed but LLM says changed=False → skips."""
    metadata = {
        "url": "https://example.com",
        "target": "产品价格",
        "content_hash": "oldhash",
        "last_semantic_summary": "价格为 $99",
    }

    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(
        return_value=MagicMock(changed=False, summary="仅格式变动", confidence="high")
    )
    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    with patch("app.scheduler.triggers.fetch_page_content", new=AsyncMock(return_value="new content")):
        with patch("app.scheduler.triggers.get_llm_with_fallback", return_value=mock_llm):
            result = await processor.should_fire(metadata)

    assert result.fired is False
    assert result.reason == "skipped"
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd backend && uv run pytest tests/scheduler/test_semantic_watcher.py -v
```
Expected: failures (TriggerResult not returned yet, processors not updated).

- [ ] **Step 4: Rewrite `triggers.py`**

Full replacement of `backend/app/scheduler/triggers.py`:

```python
"""Trigger processors for proactive monitoring.

Each processor implements should_fire(metadata) -> TriggerResult.
Metadata dict is mutated in-place to persist state (e.g., last_hash).
"""

import email as email_lib
import email.message
import hashlib
import imaplib
import ipaddress
import socket
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Literal

import httpx
import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agent.llm import get_llm_with_fallback
from app.core.config import settings
from app.core.security import fernet_decrypt
from app.scheduler.fetch import fetch_page_content
from app.scheduler.prompts import SEMANTIC_WATCHER_SYSTEM_PROMPT, SEMANTIC_WATCHER_USER_PROMPT
from app.scheduler.trigger_result import TriggerResult

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Structured output schema for SemanticWatcher
# ---------------------------------------------------------------------------

class SemanticAnalysisResult(BaseModel):
    changed: bool
    summary: str
    confidence: Literal["high", "medium", "low"]


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class TriggerProcessor(ABC):
    @abstractmethod
    async def should_fire(self, metadata: dict) -> TriggerResult:
        """Evaluate trigger condition. Mutates metadata in-place to persist state."""


# ---------------------------------------------------------------------------
# Web Watcher (hash-based)
# ---------------------------------------------------------------------------

class WebWatcherProcessor(TriggerProcessor):
    async def should_fire(self, metadata: dict) -> TriggerResult:
        url: str = metadata.get("url", "")
        http_headers: dict = metadata.get("http_headers") or {}

        try:
            text = await fetch_page_content(url, http_headers=http_headers)
        except (ValueError, httpx.HTTPError) as exc:
            logger.warning("web_watcher_fetch_failed", url=url, error=str(exc))
            return TriggerResult(fired=False, reason="error")

        new_hash = hashlib.md5(text.encode()).hexdigest()
        last_hash = metadata.get("last_hash")

        if last_hash is None:
            metadata["last_hash"] = new_hash
            return TriggerResult(fired=False, reason="first_run_initialized")

        if new_hash == last_hash:
            return TriggerResult(fired=False, reason="content_hash_unchanged")

        metadata["last_hash"] = new_hash
        return TriggerResult(
            fired=True,
            reason="fired",
            trigger_ctx={
                "trigger_type": "web_watcher",
                "url": url,
                "detected_at": datetime.now(tz=timezone.utc).isoformat(),
                "changed_summary": "网页内容已变化",
                "confidence": "high",
            },
        )


# ---------------------------------------------------------------------------
# Semantic Watcher (LLM-based)
# ---------------------------------------------------------------------------

class SemanticWatcherProcessor(TriggerProcessor):
    async def should_fire(self, metadata: dict) -> TriggerResult:
        url: str = metadata.get("url", "")
        target: str = metadata.get("target", "内容变化")
        http_headers: dict = metadata.get("http_headers") or {}
        fire_on_init: bool = metadata.get("fire_on_init", False)

        try:
            text = await fetch_page_content(url, http_headers=http_headers)
        except (ValueError, httpx.HTTPError) as exc:
            logger.warning("semantic_watcher_fetch_failed", url=url, error=str(exc))
            return TriggerResult(fired=False, reason="error")

        new_hash = hashlib.md5(text.encode()).hexdigest()
        last_summary: str | None = metadata.get("last_semantic_summary")

        # --- First run: no previous state ---
        if last_summary is None:
            metadata["content_hash"] = new_hash
            metadata["last_semantic_summary"] = text[:200]
            if fire_on_init:
                return TriggerResult(
                    fired=True,
                    reason="fired",
                    trigger_ctx={
                        "trigger_type": "semantic_watcher",
                        "url": url,
                        "target": target,
                        "detected_at": datetime.now(tz=timezone.utc).isoformat(),
                        "changed_summary": "已初始化监控",
                        "confidence": "high",
                    },
                )
            return TriggerResult(fired=False, reason="first_run_initialized")

        # --- Content hash pre-check: skip LLM if unchanged ---
        if new_hash == metadata.get("content_hash"):
            return TriggerResult(fired=False, reason="content_hash_unchanged")

        # --- LLM semantic analysis ---
        analysis = await self._analyze(target, last_summary, text)
        if analysis is None:
            return TriggerResult(fired=False, reason="llm_parse_error")

        metadata["content_hash"] = new_hash
        if analysis.changed:
            metadata["last_semantic_summary"] = analysis.summary
            return TriggerResult(
                fired=True,
                reason="fired",
                trigger_ctx={
                    "trigger_type": "semantic_watcher",
                    "url": url,
                    "target": target,
                    "detected_at": datetime.now(tz=timezone.utc).isoformat(),
                    "changed_summary": analysis.summary,
                    "confidence": analysis.confidence,
                },
            )

        return TriggerResult(fired=False, reason="skipped")

    async def _analyze(
        self, target: str, last_summary: str, new_content: str
    ) -> SemanticAnalysisResult | None:
        provider = "deepseek"
        model = "deepseek-chat"
        api_key = settings.deepseek_api_key
        if not api_key and settings.openai_api_key:
            provider = "openai"
            model = "gpt-4o-mini"
            api_key = settings.openai_api_key
        if not api_key:
            logger.warning("semantic_watcher_no_api_key")
            return None

        llm = get_llm_with_fallback(provider, model, api_key)
        messages = [
            SystemMessage(content=SEMANTIC_WATCHER_SYSTEM_PROMPT),
            HumanMessage(
                content=SEMANTIC_WATCHER_USER_PROMPT.format(
                    target=target,
                    last_summary=last_summary,
                    new_content=new_content,
                )
            ),
        ]

        # Try structured output first; fall back to JSON parsing
        try:
            structured_llm = llm.with_structured_output(SemanticAnalysisResult)
            return await structured_llm.ainvoke(messages)
        except Exception:  # noqa: BLE001
            pass

        try:
            import json
            raw = await llm.ainvoke(messages)
            data = json.loads(raw.content)
            return SemanticAnalysisResult(**data)
        except Exception as exc:
            logger.warning("semantic_watcher_llm_parse_error", error=str(exc))
            return None


# ---------------------------------------------------------------------------
# IMAP Email Processor
# ---------------------------------------------------------------------------

def _fetch_emails_since_uid(
    conn: imaplib.IMAP4 | imaplib.IMAP4_SSL,
    last_uid: int,
    max_emails: int = 10,
) -> tuple[list[email.message.Message], list[bytes]]:
    """Return (messages, uid_bytes) for UIDs > last_uid, capped at max_emails."""
    _, data = conn.uid("search", None, f"UID {last_uid + 1}:*")
    raw_uids: list[bytes] = data[0].split() if data[0] else []
    uids = raw_uids[-max_emails:]
    messages = []
    for uid in uids:
        _, raw = conn.uid("fetch", uid, "(RFC822)")
        if raw and raw[0]:
            messages.append(email_lib.message_from_bytes(raw[0][1]))
    return messages, uids


def _extract_body_snippet(msg: email.message.Message, max_chars: int = 500) -> str:
    """Extract plaintext snippet from email MIME parts."""
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace").strip()[:max_chars]
    return ""


class IMAPEmailProcessor(TriggerProcessor):
    async def should_fire(self, metadata: dict) -> TriggerResult:
        import asyncio

        return await asyncio.to_thread(self._check_imap, metadata)

    def _check_imap(self, metadata: dict) -> TriggerResult:
        host: str = metadata.get("imap_host", "")
        port: int = metadata.get("imap_port", 993)
        user: str = metadata.get("imap_user", "")
        encrypted_password: str = metadata.get("imap_password", "")
        folder: str = metadata.get("imap_folder", "INBOX")
        last_uid: int = metadata.get("last_uid", 0)

        try:
            password = fernet_decrypt(encrypted_password)
        except Exception as exc:
            logger.error("imap_decrypt_failed", error=str(exc))
            return TriggerResult(fired=False, reason="error")

        try:
            if port == 993:
                conn: imaplib.IMAP4 | imaplib.IMAP4_SSL = imaplib.IMAP4_SSL(host, port)
            else:
                conn = imaplib.IMAP4(host, port)
                conn.starttls()

            conn.login(user, password)
            conn.select(folder)

            messages, new_uids = _fetch_emails_since_uid(conn, last_uid)
            conn.logout()
        except imaplib.IMAP4.error as exc:
            logger.warning("imap_check_failed", error=str(exc))
            return TriggerResult(fired=False, reason="error")

        if not new_uids:
            return TriggerResult(fired=False, reason="no_new_emails")

        metadata["last_uid"] = max(int(uid) for uid in new_uids)

        parsed_emails = [
            {
                "from": msg.get("From", ""),
                "subject": msg.get("Subject", ""),
                "date": msg.get("Date", ""),
                "snippet": _extract_body_snippet(msg),
            }
            for msg in messages
        ]

        return TriggerResult(
            fired=True,
            reason="fired",
            trigger_ctx={
                "trigger_type": "email",
                "detected_at": datetime.now(tz=timezone.utc).isoformat(),
                "new_email_count": len(new_uids),
                "emails": parsed_emails,
            },
        )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

async def evaluate_trigger(trigger_type: str, metadata: dict) -> TriggerResult:
    """Route to the appropriate processor and return a TriggerResult."""
    match trigger_type:
        case "cron":
            return TriggerResult(fired=True, reason="fired")
        case "web_watcher":
            return await WebWatcherProcessor().should_fire(metadata)
        case "semantic_watcher":
            return await SemanticWatcherProcessor().should_fire(metadata)
        case "email":
            return await IMAPEmailProcessor().should_fire(metadata)
        case _:
            logger.warning("unknown_trigger_type", trigger_type=trigger_type)
            return TriggerResult(fired=True, reason="fired")
```

- [ ] **Step 5: Run all scheduler tests**

```bash
cd backend && uv run pytest tests/scheduler/ -v
```
Expected: all PASSED.

- [ ] **Step 6: Lint and type-check**

```bash
cd backend && uv run ruff check --fix app/scheduler/triggers.py app/scheduler/prompts.py
cd backend && uv run mypy app/scheduler/triggers.py
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/scheduler/triggers.py \
        backend/app/scheduler/prompts.py \
        backend/tests/scheduler/test_semantic_watcher.py
git commit -m "feat(monitoring): refactor trigger processors to return TriggerResult"
```

---

## Chunk 4: ARQ Worker Infrastructure

### Task 6: Add ARQ dependency + worker.py

**Files:**
- Modify: `backend/pyproject.toml` — add `arq`
- Create: `backend/app/worker.py`
- Test: `backend/tests/test_worker.py`

- [ ] **Step 1: Add arq dependency**

```bash
cd backend && uv add "arq>=0.25"
```

Verify:
```bash
cd backend && python -c "import arq; print(arq.__version__)"
```

- [ ] **Step 2: Write worker tests**

```python
# backend/tests/test_worker.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scheduler.trigger_result import TriggerResult


@pytest.mark.asyncio
async def test_execute_cron_job_fires_agent():
    """When trigger fires, agent is invoked and execution is recorded."""
    job_id = str(uuid.uuid4())
    run_group_id = str(uuid.uuid4())

    mock_job = MagicMock()
    mock_job.id = uuid.UUID(job_id)
    mock_job.user_id = uuid.uuid4()
    mock_job.task = "Check prices"
    mock_job.trigger_type = "cron"
    mock_job.trigger_metadata = {}
    mock_job.is_active = True

    fired_result = TriggerResult(
        fired=True, reason="fired", trigger_ctx={"changed_summary": "changed"}
    )

    ctx = {"redis": AsyncMock()}
    ctx["redis"].set = AsyncMock(return_value=True)   # lock acquired
    ctx["redis"].delete = AsyncMock()
    ctx["job_try"] = 1

    with patch("app.worker.AsyncSessionLocal") as mock_session_cls, \
         patch("app.worker.evaluate_trigger", new=AsyncMock(return_value=fired_result)), \
         patch("app.worker.run_agent_for_user", new=AsyncMock(return_value="done")) as mock_agent:

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = AsyncMock(return_value=mock_job)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session_cls.return_value = mock_session

        from app.worker import execute_cron_job
        await execute_cron_job(ctx, job_id=job_id, run_group_id=run_group_id)

    # run_agent_for_user was called (assert inside patch scope via captured mock)
    mock_agent.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_cron_job_lock_contention_returns_early():
    """If lock cannot be acquired, execution is skipped silently."""
    ctx = {"redis": AsyncMock()}
    ctx["redis"].set = AsyncMock(return_value=None)  # lock NOT acquired
    ctx["job_try"] = 1

    with patch("app.worker.AsyncSessionLocal"):
        from app.worker import execute_cron_job
        # Should return without raising
        await execute_cron_job(ctx, job_id=str(uuid.uuid4()), run_group_id=str(uuid.uuid4()))
```

- [ ] **Step 3: Run to verify failure**

```bash
cd backend && uv run pytest tests/test_worker.py -v
```
Expected: `ModuleNotFoundError: app.worker`.

- [ ] **Step 4: Implement `worker.py`**

```python
# backend/app/worker.py
"""ARQ worker: consumes cron job IDs from Redis queue and executes trigger evaluation."""

import time
import uuid
from datetime import datetime, timezone

import structlog
from arq.connections import RedisSettings

from app.core.config import settings
from app.db.models import CronJob, JobExecution
from app.db.session import AsyncSessionLocal
from app.gateway.agent_runner import run_agent_for_user
from app.scheduler.triggers import evaluate_trigger

logger = structlog.get_logger(__name__)

_LOCK_TTL_SECONDS = 300  # 5 minutes


async def execute_cron_job(ctx: dict, *, job_id: str, run_group_id: str) -> None:
    """
    ARQ job function. Evaluates trigger condition and optionally runs the agent.

    ctx["redis"]   — arq Redis connection (used for distributed lock)
    ctx["job_try"] — current attempt number (1-indexed, provided by ARQ)
    """
    lock_key = f"cron_lock:{job_id}"
    redis = ctx["redis"]
    attempt: int = ctx.get("job_try", 1)

    # Acquire distributed lock (NX = only set if not exists)
    acquired = await redis.set(lock_key, 1, nx=True, ex=_LOCK_TTL_SECONDS)
    if not acquired:
        logger.info("cron_job_lock_contention", job_id=job_id)
        return

    start_ms = time.monotonic()
    status = "error"
    trigger_ctx = None
    agent_result = None
    error_msg = None

    try:
        async with AsyncSessionLocal() as db:
            job: CronJob | None = await db.get(CronJob, uuid.UUID(job_id))
            if job is None or not job.is_active:
                logger.info("cron_job_not_found_or_inactive", job_id=job_id)
                return

            # Evaluate trigger (mutates metadata in-place)
            metadata: dict = job.trigger_metadata or {}
            result = await evaluate_trigger(job.trigger_type, metadata)

            if result.fired:
                status = "fired"
                trigger_ctx = result.trigger_ctx
                agent_result = await run_agent_for_user(
                    user_id=str(job.user_id),
                    task=job.task,
                    trigger_ctx=result.trigger_ctx,
                )
                agent_result = (agent_result or "")[:2000]
            else:
                status = "skipped"

            # Capture duration AFTER agent call so it includes agent execution time
            duration_ms = int((time.monotonic() - start_ms) * 1000)

            # Persist state: update metadata + last_run_at + insert execution record
            job.trigger_metadata = metadata
            job.last_run_at = datetime.now(tz=timezone.utc)

            execution = JobExecution(
                job_id=job.id,
                run_group_id=uuid.UUID(run_group_id),
                status=status,
                trigger_ctx=trigger_ctx,
                agent_result=agent_result,
                duration_ms=duration_ms,
                attempt=attempt,
            )
            db.add(execution)
            await db.commit()

            logger.info(
                "cron_job_executed",
                job_id=job_id,
                status=status,
                duration_ms=duration_ms,
            )

    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ms) * 1000)
        error_msg = str(exc)
        logger.exception("cron_job_execution_failed", job_id=job_id, error=error_msg)

        # Write error record
        try:
            async with AsyncSessionLocal() as db:
                execution = JobExecution(
                    job_id=uuid.UUID(job_id),
                    run_group_id=uuid.UUID(run_group_id),
                    status="error",
                    duration_ms=duration_ms,
                    error_msg=error_msg[:1000],
                    attempt=attempt,
                )
                db.add(execution)
                await db.commit()
        except Exception:
            logger.exception("failed_to_write_error_execution", job_id=job_id)

        raise  # Re-raise so ARQ can retry

    finally:
        await redis.delete(lock_key)


class WorkerSettings:
    functions = [execute_cron_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300
    retry_jobs = True
    max_tries = 3
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_worker.py -v
```
Expected: PASSED.

- [ ] **Step 6: Collect-only check**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/worker.py backend/tests/test_worker.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(monitoring): add ARQ worker with distributed lock and execution history"
```

---

### Task 7: Rewrite runner.py — APScheduler becomes enqueue-only

**Files:**
- Modify: `backend/app/scheduler/runner.py`

- [ ] **Step 1: Read the current `runner.py` fully before editing**

```bash
cat backend/app/scheduler/runner.py
```

- [ ] **Step 2: Rewrite `runner.py`**

Replace `_execute_cron_job` and add `arq_pool` management. The rest (register, unregister, load, start, stop) stays structurally the same but `_execute_cron_job` now just enqueues:

```python
# backend/app/scheduler/runner.py  (key changes — read full file first)
import uuid
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from sqlalchemy import select

from app.core.config import settings
from app.db.models import CronJob
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None
_arq_pool: ArqRedis | None = None


async def _execute_cron_job(job_id: str) -> None:
    """APScheduler callback: enqueue the job for ARQ worker execution."""
    global _arq_pool
    if _arq_pool is None:
        logger.error("arq_pool_not_initialized", job_id=job_id)
        return
    run_group_id = str(uuid.uuid4())
    await _arq_pool.enqueue_job(
        "execute_cron_job",
        job_id=job_id,
        run_group_id=run_group_id,
    )
    logger.info("cron_job_enqueued", job_id=job_id, run_group_id=run_group_id)


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def register_cron_job(job_id: str, schedule: str) -> None:
    from apscheduler.triggers.cron import CronTrigger

    scheduler = get_scheduler()
    job_key = f"cron_{job_id}"
    if scheduler.get_job(job_key):
        scheduler.remove_job(job_key)
    scheduler.add_job(
        _execute_cron_job,
        trigger=CronTrigger.from_crontab(schedule),
        id=job_key,
        kwargs={"job_id": job_id},
        misfire_grace_time=60,
        coalesce=True,
    )


def unregister_cron_job(job_id: str) -> None:
    scheduler = get_scheduler()
    job_key = f"cron_{job_id}"
    if scheduler.get_job(job_key):
        scheduler.remove_job(job_key)


async def _load_cron_jobs() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CronJob).where(CronJob.is_active == True))
        jobs = result.scalars().all()
    for job in jobs:
        register_cron_job(str(job.id), job.schedule)
    logger.info("cron_jobs_loaded", count=len(jobs))


async def start_scheduler() -> None:
    global _arq_pool
    _arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await _load_cron_jobs()
    get_scheduler().start()
    logger.info("scheduler_started")


async def stop_scheduler() -> None:
    global _arq_pool
    get_scheduler().shutdown(wait=False)
    if _arq_pool:
        await _arq_pool.aclose()
        _arq_pool = None
    logger.info("scheduler_stopped")
```

- [ ] **Step 3: Verify no import errors**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```

- [ ] **Step 4: Lint and type-check**

```bash
cd backend && uv run ruff check --fix app/scheduler/runner.py && uv run mypy app/scheduler/runner.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/scheduler/runner.py
git commit -m "feat(monitoring): rewrite runner.py to enqueue-only via ARQ"
```

---

## Chunk 5: API Layer

### Task 8: GET /history and POST /test endpoints + quota enforcement

**Files:**
- Modify: `backend/app/api/cron.py`
- Test: `backend/tests/api/test_cron_v2.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/api/test_cron_v2.py
"""Tests for new cron API endpoints: history, test trigger, quota."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# --- GET /api/cron/{job_id}/history ---

@pytest.mark.asyncio
async def test_history_returns_executions(client: AsyncClient, auth_headers: dict):
    """History endpoint returns list of executions for owned job."""
    # This test requires the full DB stack — skip in unit test context.
    # In integration tests: create job, manually insert executions, call endpoint.
    pass  # placeholder — integration test


@pytest.mark.asyncio
async def test_history_404_for_other_user_job(client: AsyncClient, auth_headers: dict):
    """History endpoint returns 404 for jobs not owned by current user."""
    other_job_id = str(uuid.uuid4())
    response = await client.get(
        f"/api/cron/{other_job_id}/history",
        headers=auth_headers,
    )
    assert response.status_code == 404


# --- POST /api/cron/{job_id}/test ---

@pytest.mark.asyncio
async def test_test_endpoint_404_for_other_user_job(client: AsyncClient, auth_headers: dict):
    """Test endpoint returns 404 for unowned jobs."""
    other_job_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/cron/{other_job_id}/test",
        headers=auth_headers,
    )
    assert response.status_code == 404


# --- POST /api/cron quota ---

@pytest.mark.asyncio
async def test_create_job_quota_exceeded(client: AsyncClient, auth_headers: dict):
    """Creating more than MAX_CRON_JOBS_PER_USER active jobs returns 429.

    This is an integration test that requires a live DB + authenticated client.
    It works by temporarily setting quota=0 via settings override, then attempting
    to create a job. The DB count query will return 0 (no existing jobs), but
    0 >= 0 means quota is exceeded.
    """
    # Override quota to 0 via patching settings in the cron module
    with patch("app.api.cron.settings") as mock_settings:
        mock_settings.max_cron_jobs_per_user = 0
        mock_settings.encryption_key = "placeholder"  # needed for other checks
        response = await client.post(
            "/api/cron",
            json={
                "schedule": "0 9 * * *",
                "task": "test",
                "trigger_type": "cron",
                "trigger_metadata": {},
            },
            headers=auth_headers,
        )
    assert response.status_code == 429

    # Note: if the test suite runs without a live DB, skip this test with:
    # @pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="requires DB")
```

- [ ] **Step 2: Run to verify baseline**

```bash
cd backend && uv run pytest tests/api/test_cron_v2.py -v 2>&1 | head -30
```

- [ ] **Step 3: Add new endpoints and quota to `cron.py`**

Open `backend/app/api/cron.py`. Make the following additions:

**Add imports** at the top:

```python
import asyncio
import time
from datetime import datetime, timezone

from app.db.models import JobExecution
from app.scheduler.triggers import evaluate_trigger
from app.gateway.agent_runner import run_agent_for_user
```

**Add Pydantic schemas** (after existing schemas):

```python
class JobExecutionSchema(BaseModel):
    id: uuid.UUID
    run_group_id: uuid.UUID
    fired_at: datetime
    status: str
    trigger_ctx: dict | None
    agent_result: str | None
    duration_ms: int | None
    error_msg: str | None
    attempt: int

    model_config = {"from_attributes": True}


class TestTriggerResponse(BaseModel):
    triggered: bool
    trigger_ctx: dict | None
    agent_result: str | None
    is_error: bool
    duration_ms: int
```

**Add quota check to `POST /api/cron`** (at the start of the create handler, before creating the job):

```python
    # Quota check
    from sqlalchemy import func as sql_func
    active_count = await db.scalar(
        select(sql_func.count()).where(
            CronJob.user_id == current_user.id,
            CronJob.is_active == True,
        )
    )
    if active_count >= settings.max_cron_jobs_per_user:
        raise HTTPException(
            status_code=429,
            detail=f"Job quota exceeded (max {settings.max_cron_jobs_per_user} active jobs)",
        )
```

**Add history endpoint**:

```python
@router.get("/{job_id}/history", response_model=list[JobExecutionSchema])
async def get_job_history(
    job_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify ownership
    job = await db.get(CronJob, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    # Group by run_group_id using CTE: return terminal row (highest attempt) per group
    from sqlalchemy import func as sql_func

    ranked_cte = (
        select(
            JobExecution,
            sql_func.row_number()
            .over(
                partition_by=JobExecution.run_group_id,
                order_by=JobExecution.attempt.desc(),
            )
            .label("rn"),
        )
        .where(JobExecution.job_id == job_id)
        .cte("ranked_executions")
    )
    result = await db.execute(
        select(JobExecution)
        .join(ranked_cte, JobExecution.id == ranked_cte.c.id)
        .where(ranked_cte.c.rn == 1)
        .order_by(ranked_cte.c.fired_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
```

**Add test endpoint**:

```python
@router.post("/{job_id}/test", response_model=TestTriggerResponse)
async def test_trigger(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await db.get(CronJob, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    start = time.monotonic()

    async def _run() -> tuple[bool, dict | None, str | None, bool]:
        metadata = dict(job.trigger_metadata or {})
        result = await evaluate_trigger(job.trigger_type, metadata)
        if not result.fired:
            return False, None, None, False
        agent_result = await run_agent_for_user(
            user_id=str(job.user_id),
            task=job.task,
            trigger_ctx=result.trigger_ctx,
        )
        is_error = agent_result.startswith("[Error") if agent_result else False
        return True, result.trigger_ctx, agent_result, is_error

    try:
        triggered, trigger_ctx, agent_result, is_error = await asyncio.wait_for(
            _run(), timeout=30.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Trigger evaluation timed out after 30s")

    duration_ms = int((time.monotonic() - start) * 1000)
    return TestTriggerResponse(
        triggered=triggered,
        trigger_ctx=trigger_ctx,
        agent_result=agent_result,
        is_error=is_error,
        duration_ms=duration_ms,
    )
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/api/test_cron_v2.py -v
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```

- [ ] **Step 5: Lint and type-check**

```bash
cd backend && uv run ruff check --fix app/api/cron.py && uv run mypy app/api/cron.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/cron.py backend/tests/api/test_cron_v2.py
git commit -m "feat(monitoring): add history/test endpoints and job quota enforcement"
```

---

## Chunk 6: Agent Integration

### Task 9: trigger_ctx in run_agent_for_user

**Files:**
- Modify: `backend/app/gateway/agent_runner.py`
- Test: `backend/tests/gateway/test_agent_runner_trigger_ctx.py`

- [ ] **Step 1: Write test**

```python
# backend/tests/gateway/test_agent_runner_trigger_ctx.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_trigger_ctx() -> dict:
    return {
        "trigger_type": "semantic_watcher",
        "url": "https://example.com",
        "target": "产品价格",
        "changed_summary": "价格从 $99 降至 $49",
        "confidence": "high",
    }


@pytest.mark.asyncio
async def test_trigger_ctx_injected_into_task():
    """trigger_ctx is formatted and prepended to the task string."""
    from app.gateway.agent_runner import format_trigger_context

    ctx = _make_trigger_ctx()
    result = format_trigger_context(ctx)
    assert "[触发上下文]" in result
    assert "价格从 $99 降至 $49" in result
    assert "产品价格" in result


@pytest.mark.asyncio
async def test_run_agent_without_trigger_ctx_unchanged():
    """When trigger_ctx is None, task string is unmodified."""
    from app.gateway.agent_runner import format_trigger_context

    result = format_trigger_context(None)
    assert result == ""
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/gateway/test_agent_runner_trigger_ctx.py -v
```
Expected: `ImportError: cannot import name 'format_trigger_context'`.

- [ ] **Step 3: Add `format_trigger_context` and update `run_agent_for_user`**

Open `backend/app/gateway/agent_runner.py`.

Add the helper function (before `run_agent_for_user`):

```python
def format_trigger_context(trigger_ctx: dict | None) -> str:
    """Format trigger context as a human-readable block for injection into task."""
    if not trigger_ctx:
        return ""
    lines = ["[触发上下文]"]
    trigger_type = trigger_ctx.get("trigger_type", "")
    if detected_at := trigger_ctx.get("detected_at"):
        lines.append(f"检测时间：{detected_at}")
    if trigger_type in ("semantic_watcher", "web_watcher"):
        if target := trigger_ctx.get("target"):
            lines.append(f"监控目标：{target}")
        if summary := trigger_ctx.get("changed_summary"):
            lines.append(f"检测到变化：{summary}")
        if url := trigger_ctx.get("url"):
            lines.append(f"原始页面：{url}")
    elif trigger_type == "email":
        count = trigger_ctx.get("new_email_count", 0)
        lines.append(f"新邮件数量：{count}")
        for i, em in enumerate(trigger_ctx.get("emails", [])[:3], 1):
            lines.append(f"邮件{i}：{em.get('from', '')} — {em.get('subject', '')}")
    return "\n".join(lines)
```

Update `run_agent_for_user` signature and task building:

```python
async def run_agent_for_user(
    user_id: str,
    task: str,
    trigger_ctx: dict | None = None,   # NEW
) -> str:
    ...
    # Early in the function, before building messages:
    ctx_block = format_trigger_context(trigger_ctx)
    full_task = f"{ctx_block}\n\n[用户任务]\n{task}" if ctx_block else task
    # Use full_task instead of task when building HumanMessage
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/gateway/test_agent_runner_trigger_ctx.py -v
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```

- [ ] **Step 5: Lint and type-check**

```bash
cd backend && uv run ruff check --fix app/gateway/agent_runner.py && uv run mypy app/gateway/agent_runner.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/gateway/agent_runner.py \
        backend/tests/gateway/test_agent_runner_trigger_ctx.py
git commit -m "feat(monitoring): inject trigger_ctx into agent task prompt"
```

---

## Chunk 7: Frontend

### Task 10: New form fields + semantic_watcher option

**Files:**
- Modify: `frontend/src/pages/ProactivePage.vue`
- Modify: `frontend/src/locales/zh.json` (and other locale files)

- [ ] **Step 1: Read current `ProactivePage.vue` fully**

```bash
cat frontend/src/pages/ProactivePage.vue
```

- [ ] **Step 2: Update trigger type dropdown**

In the trigger type `<select>`, add `semantic_watcher` option (it's currently missing):

```html
<option value="semantic_watcher">{{ t('proactive.triggerTypes.semantic_watcher') }}</option>
```

- [ ] **Step 3: Add conditional form fields**

In the create/edit modal, after the existing web_watcher URL field, add:

```html
<!-- semantic_watcher fields -->
<template v-if="form.trigger_type === 'semantic_watcher'">
  <div class="form-group">
    <label>{{ t('proactive.targetLabel') }}</label>
    <input
      v-model="form.target"
      type="text"
      :placeholder="t('proactive.targetPlaceholder')"
      required
    />
  </div>
  <div class="form-group">
    <label>
      <input v-model="form.use_browser" type="checkbox" />
      {{ t('proactive.useBrowser') }}
    </label>
  </div>
  <div class="form-group">
    <label>
      <input v-model="form.fire_on_init" type="checkbox" />
      {{ t('proactive.fireOnInit') }}
    </label>
  </div>
</template>

<!-- web_watcher extra fields -->
<template v-if="form.trigger_type === 'web_watcher'">
  <div class="form-group">
    <label>
      <input v-model="form.use_browser" type="checkbox" />
      {{ t('proactive.useBrowser') }}
    </label>
  </div>
</template>

<!-- email extra fields -->
<template v-if="form.trigger_type === 'email'">
  <!-- existing imap_host, imap_user, imap_password fields... -->
  <div class="form-group">
    <label>{{ t('proactive.imapFolder') }}</label>
    <input v-model="form.imap_folder" type="text" placeholder="INBOX" />
  </div>
  <div class="form-group">
    <label>{{ t('proactive.imapPort') }}</label>
    <input v-model.number="form.imap_port" type="number" placeholder="993" />
  </div>
</template>
```

- [ ] **Step 4: Update form data and `buildTriggerMetadata()`**

In the `form` reactive object, add:

```typescript
url: '',          // ← confirm this already exists for web_watcher; add if missing
target: '',
use_browser: false,
fire_on_init: false,
imap_folder: 'INBOX',
imap_port: 993,
```

Note: `form.url` is used in `buildTriggerMetadata()` for both `web_watcher` and `semantic_watcher`. Check whether it already exists in the current form object. If the existing form only uses it for `web_watcher` under a different key (e.g. `form.web_url`), add `url: ''` as a unified field and update any existing references.

Update `buildTriggerMetadata()`:

```typescript
function buildTriggerMetadata() {
  switch (form.trigger_type) {
    case 'web_watcher':
      return { url: form.url, use_browser: form.use_browser }
    case 'semantic_watcher':
      return {
        url: form.url,
        target: form.target,
        use_browser: form.use_browser,
        fire_on_init: form.fire_on_init,
      }
    case 'email':
      return {
        imap_host: form.imap_host,
        imap_user: form.imap_user,
        imap_password: form.imap_password,
        imap_folder: form.imap_folder || 'INBOX',
        imap_port: form.imap_port || 993,
      }
    default:
      return {}
  }
}
```

- [ ] **Step 5: Add i18n strings to `zh.json`**

In the `proactive` section:

```json
"targetLabel": "监控目标",
"targetPlaceholder": "产品价格、新闻标题、关键词…",
"useBrowser": "使用浏览器渲染（支持 SPA 页面）",
"fireOnInit": "创建后立即触发一次",
"imapFolder": "邮件文件夹",
"imapPort": "IMAP 端口",
"triggerTypes": {
  "cron": "定时任务",
  "web_watcher": "网页监控（哈希）",
  "semantic_watcher": "网页监控（语义）",
  "email": "邮件触发"
},
"testTrigger": "测试触发",
"testResult": "测试结果",
"history": "执行历史",
"noHistory": "暂无执行记录"
```

Add the same keys (translated) to `en.json` and other locale files.

- [ ] **Step 6: Verify frontend compiles**

```bash
cd frontend && bun run type-check
```
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ProactivePage.vue frontend/src/locales/
git commit -m "feat(monitoring): add semantic_watcher form fields and i18n strings"
```

---

### Task 11: Test trigger button

**Files:**
- Modify: `frontend/src/pages/ProactivePage.vue`

- [ ] **Step 1: Add test button to job card**

Inside each job card, alongside the delete button, add:

```html
<button
  class="btn-icon btn-test"
  :disabled="testing[job.id]"
  @click.stop="testTrigger(job)"
  :title="t('proactive.testTrigger')"
>
  <span v-if="testing[job.id]">⏳</span>
  <span v-else>▶</span>
</button>
```

- [ ] **Step 2: Add test trigger logic**

```typescript
const testing = ref<Record<string, boolean>>({})
const testResultModal = ref<{
  show: boolean
  triggered: boolean
  triggerCtx: Record<string, unknown> | null
  agentResult: string | null
  isError: boolean
  durationMs: number
}>({
  show: false,
  triggered: false,
  triggerCtx: null,
  agentResult: null,
  isError: false,
  durationMs: 0,
})

async function testTrigger(job: CronJob) {
  testing.value[job.id] = true
  try {
    const res = await api.post(`/cron/${job.id}/test`)
    testResultModal.value = {
      show: true,
      triggered: res.data.triggered,
      triggerCtx: res.data.trigger_ctx,
      agentResult: res.data.agent_result,
      isError: res.data.is_error,
      durationMs: res.data.duration_ms,
    }
  } catch (err: unknown) {
    alert(t('proactive.testFailed'))
  } finally {
    testing.value[job.id] = false
  }
}
```

- [ ] **Step 3: Add result modal**

```html
<!-- Test Result Modal -->
<div v-if="testResultModal.show" class="modal-overlay" @click.self="testResultModal.show = false">
  <div class="modal-content">
    <h3>{{ t('proactive.testResult') }}</h3>
    <p>
      <strong>{{ t('proactive.triggered') }}:</strong>
      {{ testResultModal.triggered ? '✅ 是' : '⏭ 否' }}
    </p>
    <p v-if="testResultModal.durationMs">
      <strong>耗时:</strong> {{ (testResultModal.durationMs / 1000).toFixed(1) }}s
    </p>
    <template v-if="testResultModal.triggered">
      <p v-if="testResultModal.triggerCtx">
        <strong>变化摘要:</strong> {{ testResultModal.triggerCtx['changed_summary'] }}
      </p>
      <p :class="{ 'text-error': testResultModal.isError }">
        <strong>Agent 回复:</strong> {{ testResultModal.agentResult }}
      </p>
    </template>
    <button @click="testResultModal.show = false">关闭</button>
  </div>
</div>
```

- [ ] **Step 4: Type-check**

```bash
cd frontend && bun run type-check
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ProactivePage.vue
git commit -m "feat(monitoring): add test trigger button with result modal"
```

---

### Task 12: Execution history panel

**Files:**
- Modify: `frontend/src/pages/ProactivePage.vue`

- [ ] **Step 1: Add history state and fetch function**

```typescript
interface JobExecution {
  id: string
  run_group_id: string
  fired_at: string
  status: 'fired' | 'skipped' | 'error'
  trigger_ctx: Record<string, unknown> | null
  agent_result: string | null
  duration_ms: number | null
  error_msg: string | null
  attempt: number
}

const expandedJobId = ref<string | null>(null)
const historyMap = ref<Record<string, JobExecution[]>>({})
const loadingHistory = ref<Record<string, boolean>>({})

async function toggleHistory(jobId: string) {
  if (expandedJobId.value === jobId) {
    expandedJobId.value = null
    return
  }
  expandedJobId.value = jobId
  if (historyMap.value[jobId]) return  // cached

  loadingHistory.value[jobId] = true
  try {
    const res = await api.get(`/cron/${jobId}/history?limit=10`)
    historyMap.value[jobId] = res.data
  } catch {
    historyMap.value[jobId] = []
  } finally {
    loadingHistory.value[jobId] = false
  }
}
```

- [ ] **Step 2: Add history panel to job card**

Below each job card's main content area:

```html
<!-- Click job title to toggle history -->
<div class="job-title" @click="toggleHistory(job.id)" style="cursor:pointer">
  {{ job.task.slice(0, 60) }}{{ job.task.length > 60 ? '…' : '' }}
  <span class="expand-icon">{{ expandedJobId === job.id ? '▲' : '▼' }}</span>
</div>

<!-- History panel -->
<div v-if="expandedJobId === job.id" class="history-panel">
  <div v-if="loadingHistory[job.id]" class="loading">加载中…</div>
  <div v-else-if="!historyMap[job.id]?.length" class="empty">
    {{ t('proactive.noHistory') }}
  </div>
  <table v-else class="history-table">
    <tbody>
      <tr v-for="exec in historyMap[job.id]" :key="exec.id">
        <td>{{ formatDate(exec.fired_at) }}</td>
        <td>
          <span :class="`badge badge-${exec.status}`">
            {{ exec.status === 'fired' ? '✅ 触发' : exec.status === 'skipped' ? '⏭ 跳过' : '❌ 失败' }}
          </span>
        </td>
        <td>{{ exec.trigger_ctx?.['changed_summary'] || exec.error_msg || '—' }}</td>
        <td>
          {{ exec.duration_ms ? (exec.duration_ms / 1000).toFixed(1) + 's' : '—' }}
          <span v-if="exec.attempt > 1">({{ exec.attempt }}次尝试)</span>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

- [ ] **Step 3: Add `formatDate` helper**

```typescript
function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}
```

- [ ] **Step 4: Type-check and lint**

```bash
cd frontend && bun run type-check && bun run lint:fix
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ProactivePage.vue
git commit -m "feat(monitoring): add execution history panel to job cards"
```

---

## Chunk 8: Infrastructure

### Task 13: docker-compose worker service + migration

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add worker service**

Open `docker-compose.yml`. After the `backend` service definition, add:

```yaml
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: uv run arq app.worker.WorkerSettings
    env_file: .env
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - app
      - infra
```

- [ ] **Step 2: Verify migration chain and run**

```bash
cd backend && uv run alembic history | head -5
```
Expected: the last entry should be `012 -> (head)`. If not present, check that `012_add_job_executions.py` was created in Task 2 and has `down_revision = "011"` (which exists as `011_add_api_keys.py`).

```bash
cd backend && uv run alembic upgrade head
```
Expected: `Running upgrade 011 -> 012, add job_executions table`

- [ ] **Step 3: Verify full import chain**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | tail -5
```

- [ ] **Step 4: Run full test suite**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -30
```

- [ ] **Step 5: Frontend final checks**

```bash
cd frontend && bun run type-check && bun run lint
```

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(monitoring): add ARQ worker service to docker-compose"
```

---

### Task 14: Final integration check

- [ ] **Step 1: Full backend static checks**

```bash
cd backend
uv run ruff check --fix && uv run ruff format
uv run mypy app
uv run pytest --collect-only -q
```

- [ ] **Step 2: Run full test suite**

```bash
cd backend && uv run pytest tests/ -v 2>&1 | tail -30
```

- [ ] **Step 3: Frontend checks**

```bash
cd frontend && bun run lint:fix && bun run type-check
```

- [ ] **Step 4: Final commit**

```bash
git add -p  # stage any remaining changes
git commit -m "feat(monitoring): proactive monitoring v2 complete

- ARQ worker replaces in-process APScheduler execution
- TriggerResult dataclass with trigger_ctx flows into agent
- SemanticWatcher: hash pre-check, structured JSON output, fixed first-run
- WebWatcher: trafilatura content extraction, URL validation (SSRF)
- IMAP: protocol/folder config, email content extraction, UID fix
- New job_executions table with retry grouping (run_group_id)
- GET /history and POST /test endpoints with ownership guards
- Per-user job quota enforcement (MAX_CRON_JOBS_PER_USER=20)
- Frontend: semantic_watcher fields, test button, history panel"
```
