# Skill Market Unified Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken Skill Market (empty list) with a local registry + unified install pipeline supporting MCP, SKILL.md, and Python plugins with both system-wide and personal scopes.

**Architecture:** Read `registry/index.json` from disk to populate the Skill Market UI; accept any URL or npx command via `POST /api/plugins/install`, auto-detect type, dispatch to the correct adapter, and persist to an `installed_plugins` DB table. Plugins are loaded per-request by the agent (system + personal merge) rather than from a process-global registry.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, httpx, Pydantic v2, Vue 3 + TypeScript, Pinia

**Spec:** `docs/superpowers/specs/2026-03-18-skill-market-unified-registry-design.md`

---

## File Map

**New files:**
- `registry/index.json` — curated skill registry (repo root)
- `backend/app/plugins/type_detector.py` — URL → type, plugin_id, name derivation
- `backend/app/plugins/adapters/__init__.py` — package marker
- `backend/app/plugins/adapters/mcp.py` — MCP install adapter
- `backend/app/plugins/adapters/skill_md.py` — SKILL.md install adapter
- `backend/app/plugins/adapters/python_plugin.py` — Python plugin install adapter
- `backend/alembic/versions/d4e5f6a7b8c9_add_installed_plugins.py` — migration
- `frontend/src/components/InstallFromUrlModal.vue` — URL install modal
- `backend/tests/plugins/__init__.py` — test package marker
- `backend/tests/plugins/test_type_detector.py` — unit tests for type detector
- `backend/tests/plugins/test_adapters.py` — unit tests for adapters
- `backend/tests/api/test_plugins_install.py` — integration tests for install/uninstall endpoints

**Modified files:**
- `backend/app/core/config.py` — add `installed_plugins_dir`
- `backend/app/db/models.py` — add `InstalledPlugin` model
- `backend/app/services/skill_market.py` — replace HTTP fetch with disk read; update `MarketSkillOut` schema
- `backend/app/plugins/loader.py` — add `_system_reload_lock` + `reload_system_plugins()`
- `backend/app/api/plugins.py` — add `InstalledPluginOut` schema + detect/install/uninstall/list endpoints; replace old market/install + market/uninstall
- `backend/app/api/chat.py` — load personal installed plugins per-request before calling `create_graph`
- `frontend/src/api/plugins.ts` — new types + new API functions
- `frontend/src/pages/SkillMarketPage.vue` — update to new schema; add category tabs + InstallFromUrlModal
- `frontend/src/pages/PluginsPage.vue` — add System/My installed sections below existing content (keep existing `GET /api/plugins` section)

---

## Task 1: Add `installed_plugins_dir` to config

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Add the setting**

In `backend/app/core/config.py`, add after the `skills_dir` line:

```python
# Installed plugins directory — stores downloaded .md and .py plugin files
installed_plugins_dir: str = str(Path.home() / ".jarvis" / "installed_plugins")
```

- [ ] **Step 2: Verify config imports correctly**

```bash
cd backend
uv run python -c "from app.core.config import settings; print(settings.installed_plugins_dir)"
```

Expected: prints a path ending in `.jarvis/installed_plugins`

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/config.py
git commit -m "feat(config): add installed_plugins_dir setting"
```

---

## Task 2: Add `InstalledPlugin` DB model

**Files:**
- Modify: `backend/app/db/models.py`

- [ ] **Step 1: Add the model at the end of `models.py`**

```python
class InstalledPlugin(Base):
    __tablename__ = "installed_plugins"
    __table_args__ = (
        CheckConstraint(
            "type IN ('mcp', 'skill_md', 'python_plugin')",
            name="installed_plugins_type_check",
        ),
        CheckConstraint(
            "scope IN ('system', 'personal')",
            name="installed_plugins_scope_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plugin_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    install_url: Mapped[str] = mapped_column(Text, nullable=False)
    mcp_command: Mapped[str | None] = mapped_column(String(200))
    mcp_args: Mapped[list[str] | None] = mapped_column(JSONB)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    installed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2: Verify import**

```bash
cd backend
uv run python -c "from app.db.models import InstalledPlugin; print(InstalledPlugin.__tablename__)"
```

Expected: `installed_plugins`

- [ ] **Step 3: Run mypy**

```bash
cd backend
uv run mypy app/db/models.py
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/models.py
git commit -m "feat(db): add InstalledPlugin model"
```

---

## Task 3: Write DB migration

**Files:**
- Create: `backend/alembic/versions/d4e5f6a7b8c9_add_installed_plugins.py`

- [ ] **Step 1: Verify current Alembic head**

```bash
cd backend
uv run alembic heads
```

Expected output must include `c7c0b68bab0e`. If a different head is shown, update the `down_revision` value in the migration file accordingly.

- [ ] **Step 2: Create the migration file**

```python
"""add_installed_plugins

Revision ID: d4e5f6a7b8c9
Revises: c7c0b68bab0e
Create Date: 2026-03-18 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c7c0b68bab0e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "installed_plugins",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("plugin_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("install_url", sa.Text, nullable=False),
        sa.Column("mcp_command", sa.String(200), nullable=True),
        sa.Column("mcp_args", JSONB, nullable=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column(
            "installed_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN ('mcp', 'skill_md', 'python_plugin')",
            name="installed_plugins_type_check",
        ),
        sa.CheckConstraint(
            "scope IN ('system', 'personal')",
            name="installed_plugins_scope_check",
        ),
    )
    # Personal installs: unique per user per plugin
    op.create_index(
        "installed_plugins_personal_unique",
        "installed_plugins",
        ["plugin_id", "installed_by"],
        unique=True,
        postgresql_where=sa.text("scope = 'personal'"),
    )
    # System installs: unique globally (installed_by IS NULL)
    op.create_index(
        "installed_plugins_system_unique",
        "installed_plugins",
        ["plugin_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'system'"),
    )
    # Lookup index for per-request tool loading
    op.create_index(
        "installed_plugins_scope_user",
        "installed_plugins",
        ["scope", "installed_by"],
    )


def downgrade() -> None:
    op.drop_index("installed_plugins_scope_user", table_name="installed_plugins")
    op.drop_index("installed_plugins_system_unique", table_name="installed_plugins")
    op.drop_index("installed_plugins_personal_unique", table_name="installed_plugins")
    op.drop_table("installed_plugins")
```

- [ ] **Step 3: Run migration (requires running postgres)**

```bash
cd backend
uv run alembic upgrade head
```

Expected: `Running upgrade c7c0b68bab0e -> d4e5f6a7b8c9, add_installed_plugins`

- [ ] **Step 4: Verify rollback works**

```bash
cd backend
uv run alembic downgrade -1
uv run alembic upgrade head
```

Expected: both commands succeed without errors

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/d4e5f6a7b8c9_add_installed_plugins.py
git commit -m "feat(migration): add installed_plugins table with partial unique indexes"
```

---

## Task 4: Create `registry/index.json`

**Files:**
- Create: `registry/index.json` (repo root — same level as `backend/`, `frontend/`)

- [ ] **Step 1: Create the file**

```json
{
  "version": "1",
  "skills": [
    {
      "id": "mcp-github",
      "name": "GitHub MCP Server",
      "description": "Read repos, issues, PRs, and code via GitHub API using Model Context Protocol",
      "type": "mcp",
      "source": "https://github.com/modelcontextprotocol/servers",
      "install_url": "npx @modelcontextprotocol/server-github",
      "author": "Anthropic",
      "tags": ["dev", "github", "mcp"],
      "scope": ["system", "personal"]
    },
    {
      "id": "mcp-filesystem",
      "name": "Filesystem MCP Server",
      "description": "Read and write files on the host filesystem via Model Context Protocol",
      "type": "mcp",
      "source": "https://github.com/modelcontextprotocol/servers",
      "install_url": "npx @modelcontextprotocol/server-filesystem",
      "author": "Anthropic",
      "tags": ["files", "mcp"],
      "scope": ["system"]
    },
    {
      "id": "mcp-brave-search",
      "name": "Brave Search MCP Server",
      "description": "Web and local search via Brave Search API using Model Context Protocol",
      "type": "mcp",
      "source": "https://github.com/modelcontextprotocol/servers",
      "install_url": "npx @modelcontextprotocol/server-brave-search",
      "author": "Anthropic",
      "tags": ["search", "web", "mcp"],
      "scope": ["system", "personal"]
    }
  ]
}
```

- [ ] **Step 2: Verify JSON parses**

```bash
python3 -c "import json; d=json.load(open('registry/index.json')); print(len(d['skills']), 'skills')"
```

Expected: `3 skills`

- [ ] **Step 3: Commit**

```bash
git add registry/index.json
git commit -m "feat(registry): add initial curated skill registry with 3 MCP entries"
```

---

## Task 5: Update `skill_market.py` — disk read + new schema

**Files:**
- Modify: `backend/app/services/skill_market.py`

- [ ] **Step 1: Rewrite the file**

`skill_market.py` lives at `backend/app/services/skill_market.py`. The `registry/index.json` is at the repo root, which is 4 levels up from this file's location (`backend/app/services/` → `backend/app/` → `backend/` → repo root). The resolved path is `Path(__file__).parents[3] / "registry" / "index.json"`.

Replace the entire contents:

```python
"""Skill Market service — reads curated registry from disk."""

import json
from pathlib import Path
from typing import Literal

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# Resolved at import time: backend/app/services/skill_market.py → [0]=services [1]=app [2]=backend [3]=repo-root
_REGISTRY_PATH = Path(__file__).parents[3] / "registry" / "index.json"


class MarketSkillOut(BaseModel):
    id: str
    name: str
    description: str
    type: Literal["mcp", "skill_md", "python_plugin"]
    install_url: str
    source: str | None = None
    author: str
    tags: list[str]
    scope: list[Literal["system", "personal"]]


# Backward-compat alias — existing code that imports MarketSkill still works
MarketSkill = MarketSkillOut


class SkillMarketManager:
    def __init__(self) -> None:
        self._registry_path = _REGISTRY_PATH

    async def fetch_registry(self) -> list[MarketSkillOut]:
        """Read the curated registry from disk."""
        try:
            if not self._registry_path.exists():
                logger.warning(
                    "market_registry_not_found", path=str(self._registry_path)
                )
                return []
            data = json.loads(self._registry_path.read_text())
            return [MarketSkillOut(**item) for item in data.get("skills", [])]
        except Exception as e:
            logger.error("market_registry_error", error=str(e))
            return []


skill_market_manager = SkillMarketManager()
```

- [ ] **Step 2: Verify path resolves to the registry file**

```bash
cd backend
uv run python -c "
import asyncio
from app.services.skill_market import skill_market_manager, _REGISTRY_PATH
print('Registry path:', _REGISTRY_PATH)
print('Exists:', _REGISTRY_PATH.exists())
skills = asyncio.run(skill_market_manager.fetch_registry())
print(len(skills), 'skills loaded')
for s in skills:
    print(' -', s.id, s.type)
"
```

Expected: path ends in `registry/index.json`, exists=True, 3 skills printed

- [ ] **Step 3: Run ruff and mypy**

```bash
cd backend
uv run ruff check --fix app/services/skill_market.py
uv run mypy app/services/skill_market.py
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/skill_market.py
git commit -m "feat(skill-market): replace HTTP registry fetch with local disk read; update schema"
```

---

## Task 6: Create type detector (TDD)

**Files:**
- Create: `backend/tests/plugins/__init__.py`
- Create: `backend/tests/plugins/test_type_detector.py`
- Create: `backend/app/plugins/type_detector.py`

- [ ] **Step 1: Create test package marker**

Create `backend/tests/plugins/__init__.py` (empty file).

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/plugins/test_type_detector.py`:

```python
"""Tests for URL type detector and plugin_id/name derivation."""

import pytest

from app.plugins.type_detector import DetectionResult, detect_type


@pytest.mark.parametrize(
    "url,expected_type",
    [
        ("https://example.com/weather.md", "skill_md"),
        ("https://raw.githubusercontent.com/user/repo/main/SKILL.md", "skill_md"),
        ("https://example.com/myplugin.py", "python_plugin"),
        ("https://example.com/bundle.zip", "python_plugin"),
        ("https://github.com/user/repo/archive/refs/heads/main.zip", "python_plugin"),
        ("npx @modelcontextprotocol/server-github", "mcp"),
        ("npx some-package", "mcp"),
        ("mcp://some-server", "mcp"),
    ],
)
def test_detect_type_by_pattern(url: str, expected_type: str) -> None:
    result = detect_type(url)
    assert result is not None
    assert result.type == expected_type


def test_unrecognized_url_returns_none() -> None:
    result = detect_type("https://example.com/something")
    assert result is None


def test_plugin_id_skill_md() -> None:
    result = detect_type("https://example.com/path/weather.md")
    assert result is not None
    assert result.plugin_id == "weather"


def test_plugin_id_python_plugin() -> None:
    result = detect_type("https://example.com/my_plugin.py")
    assert result is not None
    assert result.plugin_id == "my-plugin"


def test_plugin_id_mcp_npx_with_scope() -> None:
    result = detect_type("npx @modelcontextprotocol/server-github")
    assert result is not None
    assert result.plugin_id == "mcp-server-github"


def test_plugin_id_mcp_npx_no_scope() -> None:
    result = detect_type("npx some-package")
    assert result is not None
    assert result.plugin_id == "mcp-some-package"


def test_default_name_from_skill_md_url() -> None:
    result = detect_type("https://example.com/weather_query.md")
    assert result is not None
    assert result.default_name == "Weather Query"


def test_default_name_from_mcp_npx() -> None:
    result = detect_type("npx @modelcontextprotocol/server-github")
    assert result is not None
    assert result.default_name == "Server Github"
```

- [ ] **Step 3: Run tests to confirm they FAIL**

```bash
cd backend
uv run pytest tests/plugins/test_type_detector.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'app.plugins.type_detector'`

- [ ] **Step 4: Implement the type detector**

Create `backend/app/plugins/type_detector.py`:

```python
"""URL type detection and plugin_id/name derivation for skill installation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlparse

PluginType = Literal["mcp", "skill_md", "python_plugin"]


@dataclass
class DetectionResult:
    type: PluginType
    plugin_id: str
    default_name: str


def _stem_from_url(url: str) -> str:
    """Extract the filename stem from a URL path."""
    path = urlparse(url).path.rstrip("/")
    return PurePosixPath(path).stem.lower()


def _slugify(text: str) -> str:
    """Lowercase, replace non-alphanumeric runs with hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _title_from_slug(slug: str) -> str:
    """Convert a slug to title-cased words."""
    return " ".join(w.capitalize() for w in re.split(r"[-_]+", slug))


def detect_type(url_or_command: str) -> DetectionResult | None:
    """Detect plugin type from a URL or npx command.

    Returns None when the type cannot be determined by pattern alone
    (bare GitHub repo URL or completely unrecognized input).
    """
    s = url_or_command.strip()

    # MCP: npx command
    if s.startswith("npx "):
        package = s[4:].strip()
        bare = re.sub(r"^@[^/]+/", "", package)
        plugin_id = "mcp-" + _slugify(bare)
        return DetectionResult(
            type="mcp",
            plugin_id=plugin_id,
            default_name=_title_from_slug(_slugify(bare)),
        )

    # MCP: mcp:// scheme
    if s.startswith("mcp://"):
        host = urlparse(s).netloc or s[6:]
        plugin_id = "mcp-" + _slugify(host)
        return DetectionResult(
            type="mcp",
            plugin_id=plugin_id,
            default_name=_title_from_slug(_slugify(host)),
        )

    # Must be an http(s) URL from here
    try:
        parsed = urlparse(s)
        if not parsed.scheme.startswith("http"):
            return None
    except Exception:
        return None

    path_lower = parsed.path.lower()

    if path_lower.endswith(".md"):
        stem = _stem_from_url(s)
        return DetectionResult(
            type="skill_md",
            plugin_id=_slugify(stem),
            default_name=_title_from_slug(stem),
        )

    if path_lower.endswith(".py"):
        stem = _stem_from_url(s)
        return DetectionResult(
            type="python_plugin",
            plugin_id=_slugify(stem),
            default_name=_title_from_slug(stem),
        )

    if path_lower.endswith(".zip") or "archive" in path_lower:
        stem = _stem_from_url(s)
        return DetectionResult(
            type="python_plugin",
            plugin_id=_slugify(stem),
            default_name=_title_from_slug(stem),
        )

    return None
```

- [ ] **Step 5: Run tests to confirm they PASS**

```bash
cd backend
uv run pytest tests/plugins/test_type_detector.py -v
```

Expected: all 10 tests pass

- [ ] **Step 6: Run ruff and mypy**

```bash
cd backend
uv run ruff check --fix app/plugins/type_detector.py
uv run mypy app/plugins/type_detector.py
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/plugins/type_detector.py backend/tests/plugins/
git commit -m "feat(plugins): add URL type detector with TDD test coverage"
```

---

## Task 7: Create adapters package (TDD)

**Files:**
- Create: `backend/app/plugins/adapters/__init__.py`
- Create: `backend/app/plugins/adapters/mcp.py`
- Create: `backend/app/plugins/adapters/skill_md.py`
- Create: `backend/app/plugins/adapters/python_plugin.py`
- Create: `backend/tests/plugins/test_adapters.py`

- [ ] **Step 1: Write failing adapter tests first**

Create `backend/tests/plugins/test_adapters.py`:

```python
"""Tests for install adapters."""

import io
import zipfile

import pytest
import respx
import httpx

from app.plugins.adapters.mcp import parse_mcp_command
from app.plugins.adapters.skill_md import download_skill_md, extract_md_title
from app.plugins.adapters.python_plugin import download_python_plugin


# ── MCP adapter ──────────────────────────────────────────────────────────────

def test_parse_mcp_basic() -> None:
    cmd, args = parse_mcp_command("npx @modelcontextprotocol/server-github")
    assert cmd == "npx"
    assert args == ["@modelcontextprotocol/server-github"]


def test_parse_mcp_with_flags() -> None:
    cmd, args = parse_mcp_command("npx -y some-package --flag")
    assert cmd == "npx"
    assert args == ["-y", "some-package", "--flag"]


def test_parse_mcp_invalid_raises() -> None:
    with pytest.raises(ValueError, match="must start with 'npx'"):
        parse_mcp_command("pip install something")


# ── skill_md adapter ──────────────────────────────────────────────────────────

def test_extract_md_title_from_heading() -> None:
    content = "# Weather Query\n\nSome description."
    assert extract_md_title(content) == "Weather Query"


def test_extract_md_title_no_heading() -> None:
    content = "No heading here\nJust text."
    assert extract_md_title(content) is None


@pytest.mark.anyio
@respx.mock
async def test_download_skill_md(tmp_path):
    url = "https://example.com/weather.md"
    md_content = "# Weather\n\n## Description\nGet weather."
    respx.get(url).mock(return_value=httpx.Response(200, text=md_content))

    dest = tmp_path / "weather.md"
    content = await download_skill_md(url, dest)

    assert dest.exists()
    assert dest.read_text() == md_content
    assert content == md_content


@pytest.mark.anyio
@respx.mock
async def test_download_skill_md_network_error(tmp_path):
    url = "https://example.com/missing.md"
    respx.get(url).mock(return_value=httpx.Response(404))

    dest = tmp_path / "missing.md"
    with pytest.raises(httpx.HTTPStatusError):
        await download_skill_md(url, dest)


# ── python_plugin adapter ─────────────────────────────────────────────────────

@pytest.mark.anyio
@respx.mock
async def test_download_python_plugin_py(tmp_path):
    url = "https://example.com/myplugin.py"
    py_content = "def hello(): return 'world'"
    respx.get(url).mock(return_value=httpx.Response(200, content=py_content.encode()))

    saved_path, manifest_name = await download_python_plugin(url, tmp_path)

    assert saved_path.exists()
    assert saved_path.name == "myplugin.py"
    assert manifest_name is None


@pytest.mark.anyio
@respx.mock
async def test_download_python_plugin_zip(tmp_path):
    url = "https://example.com/mypkg.zip"
    # Build a small zip in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.yaml", "name: My Plugin\nversion: 1.0")
        z.writestr("__init__.py", "")
    buf.seek(0)

    respx.get(url).mock(return_value=httpx.Response(200, content=buf.read()))

    saved_path, manifest_name = await download_python_plugin(url, tmp_path)

    assert saved_path.is_dir()
    assert manifest_name == "My Plugin"
```

- [ ] **Step 2: Run tests to confirm they FAIL**

```bash
cd backend
uv run pytest tests/plugins/test_adapters.py -v 2>&1 | head -15
```

Expected: `ModuleNotFoundError: No module named 'app.plugins.adapters'`

- [ ] **Step 3: Create `adapters/__init__.py`** (empty)

- [ ] **Step 4: Create `mcp.py`**

Create `backend/app/plugins/adapters/mcp.py`:

```python
"""MCP install adapter — parses npx commands."""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def parse_mcp_command(install_url: str) -> tuple[str, list[str]]:
    """Parse an npx command into (command, args).

    Examples:
        "npx @modelcontextprotocol/server-github" → ("npx", ["@modelcontextprotocol/server-github"])
        "npx -y pkg --flag" → ("npx", ["-y", "pkg", "--flag"])
    """
    parts = install_url.strip().split()
    if not parts or parts[0] != "npx":
        raise ValueError(f"MCP install_url must start with 'npx', got: {install_url!r}")
    return parts[0], parts[1:]
```

- [ ] **Step 5: Create `skill_md.py`**

Create `backend/app/plugins/adapters/skill_md.py`:

```python
"""SKILL.md install adapter — downloads and saves .md files."""

from __future__ import annotations

from pathlib import Path

import httpx
import structlog

logger = structlog.get_logger(__name__)

_FETCH_TIMEOUT = 10.0


async def download_skill_md(url: str, dest_path: Path) -> str:
    """Download a .md skill file and write it to dest_path. Returns the content.

    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=_FETCH_TIMEOUT) as client:
        response = await client.get(url)
        response.raise_for_status()
        content = response.text
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(content, encoding="utf-8")
        logger.info("skill_md_downloaded", url=url, path=str(dest_path))
        return content


def extract_md_title(content: str) -> str | None:
    """Extract the first # heading from Markdown content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None
```

- [ ] **Step 6: Create `python_plugin.py`**

Create `backend/app/plugins/adapters/python_plugin.py`:

```python
"""Python plugin install adapter — downloads .py or .zip files."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import structlog
import yaml

logger = structlog.get_logger(__name__)

_FETCH_TIMEOUT = 30.0


async def download_python_plugin(url: str, dest_dir: Path) -> tuple[Path, str | None]:
    """Download a .py or .zip plugin. Returns (saved_path, manifest_name_or_None).

    For .py: saves to dest_dir/<filename>.py
    For .zip: extracts to dest_dir/<pkg_name>/, reads manifest.yaml name if present.
    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=_FETCH_TIMEOUT) as client:
        response = await client.get(url)
        response.raise_for_status()
        dest_dir.mkdir(parents=True, exist_ok=True)

        clean_path = url.split("?")[0].rstrip("/")
        if clean_path.lower().endswith(".py"):
            filename = clean_path.split("/")[-1]
            dest_path = dest_dir / filename
            dest_path.write_bytes(response.content)
            logger.info("python_plugin_downloaded", url=url, path=str(dest_path))
            return dest_path, None

        # ZIP
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            pkg_name = (
                clean_path.split("/")[-1]
                .replace(".zip", "")
                .replace(".main", "")
                .replace(".master", "")
            )
            pkg_dir = dest_dir / pkg_name
            z.extractall(pkg_dir)
            manifest_name = _read_manifest_name(pkg_dir)
            logger.info("python_plugin_extracted", url=url, path=str(pkg_dir))
            return pkg_dir, manifest_name


def _read_manifest_name(pkg_dir: Path) -> str | None:
    """Read the name field from manifest.yaml if present."""
    manifest_path = pkg_dir / "manifest.yaml"
    if not manifest_path.exists():
        candidates = list(pkg_dir.glob("*/manifest.yaml"))
        if not candidates:
            return None
        manifest_path = candidates[0]
    try:
        data = yaml.safe_load(manifest_path.read_text())
        return data.get("name")
    except Exception:
        return None
```

- [ ] **Step 7: Check if `respx` and `anyio` are available**

```bash
cd backend
uv run python -c "import respx, anyio; print('ok')"
```

If not available, add them:

```bash
uv add --group dev respx anyio pytest-anyio
```

- [ ] **Step 8: Run tests to confirm they PASS**

```bash
cd backend
uv run pytest tests/plugins/test_adapters.py -v
```

Expected: all 8 tests pass

- [ ] **Step 9: Run ruff and mypy**

```bash
cd backend
uv run ruff check --fix app/plugins/adapters/
uv run mypy app/plugins/adapters/
```

- [ ] **Step 10: Commit**

```bash
git add backend/app/plugins/adapters/ backend/tests/plugins/test_adapters.py
git commit -m "feat(plugins): add MCP, skill_md, and python_plugin install adapters with TDD tests"
```

---

## Task 8: Add `reload_system_plugins` to loader

**Files:**
- Modify: `backend/app/plugins/loader.py`

The existing reload pattern in `app/api/plugins.py` is:
```python
await deactivate_all_plugins(plugin_registry)
plugin_registry._entries.clear()
await load_all_plugins(plugin_registry)
await activate_all_plugins(plugin_registry)
```
These are module-level functions (not registry methods) that take `registry` as their first argument. The new function wraps this pattern with an asyncio lock.

- [ ] **Step 1: Add `asyncio` import**

Check the existing imports in `loader.py` and add `import asyncio` if not already present.

- [ ] **Step 2: Add the lock and function**

After `_DEFAULT_PLUGIN_DIR = Path.home() / ".jarvis" / "plugins"`, add:

```python
# Protects system plugin reload against concurrent admin installs
_system_reload_lock = asyncio.Lock()


async def reload_system_plugins(registry: PluginRegistry) -> None:
    """Reload system plugins under a lock to prevent concurrent reload races."""
    async with _system_reload_lock:
        await deactivate_all_plugins(registry)
        registry._entries.clear()
        await load_all_plugins(registry)
        await activate_all_plugins(registry)
```

- [ ] **Step 3: Verify function is importable**

```bash
cd backend
uv run python -c "from app.plugins.loader import reload_system_plugins; print('ok')"
```

- [ ] **Step 4: Run ruff and mypy**

```bash
cd backend
uv run ruff check --fix app/plugins/loader.py
uv run mypy app/plugins/loader.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/loader.py
git commit -m "feat(plugins): add reload_system_plugins with asyncio lock"
```

---

## Task 9: Add new API endpoints + install integration tests (TDD)

**Files:**
- Create: `backend/tests/api/test_plugins_install.py`
- Modify: `backend/app/api/plugins.py`

- [ ] **Step 1: Write failing integration tests first**

Create `backend/tests/api/test_plugins_install.py`:

```python
"""Integration tests for the unified plugin install/uninstall/list endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.db.models import InstalledPlugin


@pytest.mark.anyio
async def test_detect_endpoint_mcp(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get(
        "/api/plugins/detect?url=npx+%40modelcontextprotocol%2Fserver-github",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["type"] == "mcp"


@pytest.mark.anyio
async def test_detect_endpoint_skill_md(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get(
        "/api/plugins/detect?url=https%3A%2F%2Fexample.com%2Fweather.md",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["type"] == "skill_md"


@pytest.mark.anyio
async def test_detect_endpoint_unrecognized(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get(
        "/api/plugins/detect?url=https%3A%2F%2Fexample.com%2Fsomething",
        headers=auth_headers,
    )
    assert response.status_code == 422
    data = response.json()
    assert "candidates" in data["detail"]


@pytest.mark.anyio
async def test_install_mcp_personal(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/api/plugins/install",
        json={"url": "npx @modelcontextprotocol/server-github", "scope": "personal"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["plugin_id"] == "mcp-server-github"
    assert data["scope"] == "personal"
    assert data["type"] == "mcp"


@pytest.mark.anyio
async def test_install_mcp_duplicate_returns_409(
    client: AsyncClient, auth_headers: dict
) -> None:
    payload = {"url": "npx @modelcontextprotocol/server-github", "scope": "personal"}
    await client.post("/api/plugins/install", json=payload, headers=auth_headers)
    response = await client.post("/api/plugins/install", json=payload, headers=auth_headers)
    assert response.status_code == 409


@pytest.mark.anyio
async def test_install_system_requires_admin(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Regular user cannot install system-scope plugin."""
    response = await client.post(
        "/api/plugins/install",
        json={"url": "npx some-pkg", "scope": "system"},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_install_system_as_admin(
    client: AsyncClient, admin_auth_headers: dict
) -> None:
    response = await client.post(
        "/api/plugins/install",
        json={"url": "npx some-pkg", "scope": "system"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["scope"] == "system"


@pytest.mark.anyio
async def test_list_installed(client: AsyncClient, auth_headers: dict) -> None:
    # Install one personal plugin first
    await client.post(
        "/api/plugins/install",
        json={"url": "npx test-pkg-list", "scope": "personal"},
        headers=auth_headers,
    )
    response = await client.get("/api/plugins/installed", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "system" in data
    assert "personal" in data
    assert any(p["plugin_id"] == "mcp-test-pkg-list" for p in data["personal"])


@pytest.mark.anyio
async def test_uninstall_personal(client: AsyncClient, auth_headers: dict) -> None:
    install_resp = await client.post(
        "/api/plugins/install",
        json={"url": "npx pkg-to-delete", "scope": "personal"},
        headers=auth_headers,
    )
    plugin_id = install_resp.json()["id"]
    response = await client.delete(f"/api/plugins/install/{plugin_id}", headers=auth_headers)
    assert response.status_code == 204


@pytest.mark.anyio
async def test_uninstall_other_user_forbidden(
    client: AsyncClient, auth_headers: dict, second_user_auth_headers: dict
) -> None:
    """User A cannot uninstall User B's personal plugin."""
    install_resp = await client.post(
        "/api/plugins/install",
        json={"url": "npx pkg-user-a", "scope": "personal"},
        headers=auth_headers,
    )
    plugin_id = install_resp.json()["id"]
    response = await client.delete(
        f"/api/plugins/install/{plugin_id}", headers=second_user_auth_headers
    )
    assert response.status_code == 403
```

> **Note:** The tests above assume that `client`, `auth_headers`, `admin_auth_headers`, and `second_user_auth_headers` fixtures exist in `conftest.py`. Check `backend/tests/conftest.py` to confirm fixture names. If `admin_auth_headers` or `second_user_auth_headers` don't exist, add them following the same pattern as existing auth fixtures.

- [ ] **Step 2: Run tests to confirm they FAIL**

```bash
cd backend
uv run pytest tests/api/test_plugins_install.py -v 2>&1 | head -15
```

Expected: failures due to missing endpoints (404) or import errors

- [ ] **Step 3: Add `InstalledPluginOut` schema to `plugins.py`**

At the top of the Pydantic schema section in `backend/app/api/plugins.py`, add:

```python
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.models import InstalledPlugin
from app.plugins.adapters.mcp import parse_mcp_command
from app.plugins.adapters.skill_md import download_skill_md, extract_md_title
from app.plugins.adapters.python_plugin import download_python_plugin
from app.plugins.loader import reload_system_plugins
from app.plugins.type_detector import DetectionResult, detect_type
from app.services.skill_market import MarketSkillOut


class InstallRequest(BaseModel):
    url: str
    type: Literal["mcp", "skill_md", "python_plugin"] | None = None
    scope: Literal["system", "personal"]


class InstalledPluginOut(BaseModel):
    id: str
    plugin_id: str
    name: str
    type: str
    install_url: str
    scope: str
    installed_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Remove old market install/uninstall endpoints, update market/skills**

Delete `install_market_skill` and `uninstall_market_skill` function bodies.

Update the `list_market_skills` import and response model:

```python
@router.get("/market/skills", response_model=list[MarketSkillOut])
async def list_market_skills(
    user: User = Depends(get_current_user),
) -> list[MarketSkillOut]:
    """Fetch available skills from the local registry."""
    return await skill_market_manager.fetch_registry()
```

- [ ] **Step 5: Add detect endpoint**

```python
@router.get("/detect")
async def detect_plugin_type(
    url: str,
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Auto-detect plugin type from a URL or npx command."""
    result = detect_type(url)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail={"msg": "Cannot determine type", "candidates": ["mcp", "skill_md", "python_plugin"]},
        )
    return {"type": result.type}
```

- [ ] **Step 6: Add unified install endpoint**

```python
@router.post("/install", response_model=InstalledPluginOut)
async def install_plugin_unified(
    req: InstallRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InstalledPlugin:
    """Install a plugin/skill from a URL or npx command."""
    if req.scope == "system" and user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin required for system scope")

    # Resolve type + derive plugin_id and default name
    detection = detect_type(req.url)
    if req.type:
        detected_type = req.type
        plugin_id = detection.plugin_id if detection else req.url.split("/")[-1].split(".")[0]
        default_name = detection.default_name if detection else plugin_id.replace("-", " ").title()
    else:
        if detection is None:
            raise HTTPException(
                status_code=422,
                detail={"msg": "Cannot determine type", "candidates": ["mcp", "skill_md", "python_plugin"]},
            )
        detected_type = detection.type
        plugin_id = detection.plugin_id
        default_name = detection.default_name

    installed_plugins_dir = Path(settings.installed_plugins_dir)
    mcp_command: str | None = None
    mcp_args: list[str] | None = None
    name = default_name

    if detected_type == "mcp":
        mcp_command, mcp_args = parse_mcp_command(req.url)

    elif detected_type == "skill_md":
        scope_dir = (
            installed_plugins_dir / "system"
            if req.scope == "system"
            else installed_plugins_dir / "users" / str(user.id)
        )
        try:
            content = await download_skill_md(req.url, scope_dir / f"{plugin_id}.md")
            md_title = extract_md_title(content)
            if md_title:
                name = md_title
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not fetch URL: {e}") from e

    elif detected_type == "python_plugin":
        scope_dir = (
            installed_plugins_dir / "system"
            if req.scope == "system"
            else installed_plugins_dir / "users" / str(user.id)
        )
        try:
            _, manifest_name = await download_python_plugin(req.url, scope_dir)
            if manifest_name:
                name = manifest_name
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not fetch URL: {e}") from e

    installed_by = None if req.scope == "system" else user.id
    row = InstalledPlugin(
        plugin_id=plugin_id,
        name=name,
        type=detected_type,
        install_url=req.url,
        mcp_command=mcp_command,
        mcp_args=mcp_args,
        scope=req.scope,
        installed_by=installed_by,
    )
    db.add(row)
    try:
        await db.commit()
        await db.refresh(row)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Already installed")

    if req.scope == "system":
        await reload_system_plugins(plugin_registry)

    return row
```

- [ ] **Step 7: Add uninstall endpoint**

```python
@router.delete("/install/{installed_plugin_id}", status_code=204)
async def uninstall_plugin(
    installed_plugin_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Uninstall a plugin. Admin for system scope; owner for personal scope."""
    result = await db.execute(
        select(InstalledPlugin).where(InstalledPlugin.id == installed_plugin_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    if row.scope == "system" and user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    if row.scope == "personal" and row.installed_by != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if row.type in ("skill_md", "python_plugin"):
        base = (
            Path(settings.installed_plugins_dir) / "system"
            if row.scope == "system"
            else Path(settings.installed_plugins_dir) / "users" / str(row.installed_by)
        )
        for candidate in [
            base / f"{row.plugin_id}.md",
            base / f"{row.plugin_id}.py",
            base / row.plugin_id,
        ]:
            if candidate.exists():
                if candidate.is_dir():
                    import shutil
                    shutil.rmtree(candidate)
                else:
                    candidate.unlink()
                break

    await db.delete(row)
    await db.commit()
    if row.scope == "system":
        await reload_system_plugins(plugin_registry)
```

- [ ] **Step 8: Add list installed endpoint**

```python
@router.get("/installed")
async def list_installed_plugins(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[InstalledPluginOut]]:
    """List installed plugins: system (all users) + personal (own only)."""
    system_result = await db.execute(
        select(InstalledPlugin).where(InstalledPlugin.scope == "system")
    )
    personal_result = await db.execute(
        select(InstalledPlugin).where(
            InstalledPlugin.scope == "personal",
            InstalledPlugin.installed_by == user.id,
        )
    )
    return {
        "system": [InstalledPluginOut.model_validate(r) for r in system_result.scalars().all()],
        "personal": [InstalledPluginOut.model_validate(r) for r in personal_result.scalars().all()],
    }
```

- [ ] **Step 9: Run collect-only to catch registration errors**

```bash
cd backend
uv run pytest --collect-only -q 2>&1 | tail -5
```

Expected: no errors

- [ ] **Step 10: Run ruff and mypy**

```bash
cd backend
uv run ruff check --fix app/api/plugins.py
uv run mypy app/api/plugins.py
```

- [ ] **Step 11: Run the install tests (requires running postgres)**

```bash
cd backend
uv run pytest tests/api/test_plugins_install.py -v
```

Expected: all tests pass

- [ ] **Step 12: Commit**

```bash
git add backend/app/api/plugins.py backend/tests/api/test_plugins_install.py
git commit -m "feat(api): add detect/install/uninstall/list-installed endpoints with integration tests"
```

---

## Task 10: Per-request personal plugin loading in chat

**Files:**
- Modify: `backend/app/api/chat.py`

The `create_graph()` call already accepts `plugin_tools: list[BaseTool] | None`. We add a helper that loads personal installed plugins (skill_md + python_plugin types) from the filesystem for the current user.

- [ ] **Step 1: Find the `create_graph` call in `chat.py`**

```bash
cd backend
grep -n "create_graph\|plugin_tools\|plugin_registry" app/api/chat.py
```

Note the line numbers.

- [ ] **Step 2: Add import**

Add to `chat.py` imports (check for duplicates first):

```python
from pathlib import Path

from app.core.config import settings
from app.db.models import InstalledPlugin
```

- [ ] **Step 3: Add the helper function**

Add before the route handler functions:

```python
async def _load_personal_plugin_tools(
    user_id: str, db: AsyncSession
) -> list[BaseTool]:
    """Load personal installed skill_md/python_plugin tools for this request."""
    from app.plugins.api import PluginAPI
    from app.plugins.loader import load_all_plugins
    from app.plugins.registry import PluginRegistry

    result = await db.execute(
        select(InstalledPlugin).where(
            InstalledPlugin.scope == "personal",
            InstalledPlugin.installed_by == user_id,
            InstalledPlugin.type.in_(["skill_md", "python_plugin"]),
        )
    )
    if not result.scalars().all():
        return []

    personal_dir = Path(settings.installed_plugins_dir) / "users" / str(user_id)
    if not personal_dir.exists():
        return []

    personal_registry = PluginRegistry()
    await load_all_plugins(personal_registry, plugin_dirs=[personal_dir])
    return personal_registry.get_all_tools()
```

- [ ] **Step 4: Call the helper before `create_graph`**

In the streaming chat handler, add before the `create_graph(...)` call:

```python
personal_tools = await _load_personal_plugin_tools(str(current_user.id), db)
```

Then pass it to `create_graph`:

```python
plugin_tools = [*existing_plugin_tools, *personal_tools]
```

(If `plugin_tools` is already being passed, append to it. If not, set `plugin_tools=personal_tools`.)

- [ ] **Step 5: Run collect-only and mypy**

```bash
cd backend
uv run pytest --collect-only -q 2>&1 | tail -5
uv run ruff check --fix app/api/chat.py
uv run mypy app/api/chat.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/chat.py
git commit -m "feat(chat): load personal installed plugins per-request before creating agent graph"
```

---

## Task 11: Update frontend API types

**Files:**
- Modify: `frontend/src/api/plugins.ts`

- [ ] **Step 1: Add new interfaces**

In `frontend/src/api/plugins.ts`, add after the existing interfaces:

```typescript
export interface MarketSkillOut {
  id: string
  name: string
  description: string
  type: 'mcp' | 'skill_md' | 'python_plugin'
  install_url: string
  source?: string
  author: string
  tags: string[]
  scope: ('system' | 'personal')[]
}

export interface InstalledPluginOut {
  id: string
  plugin_id: string
  name: string
  type: 'mcp' | 'skill_md' | 'python_plugin'
  install_url: string
  scope: 'system' | 'personal'
  installed_by: string | null
  created_at: string
}

export interface InstallRequest {
  url: string
  type?: 'mcp' | 'skill_md' | 'python_plugin'
  scope: 'system' | 'personal'
}

export interface InstalledListResponse {
  system: InstalledPluginOut[]
  personal: InstalledPluginOut[]
}
```

Add the `marketApi` export object:

```typescript
export const marketApi = {
  listSkills: () => api.get<MarketSkillOut[]>('/plugins/market/skills'),
  detect: (url: string) =>
    api.get<{ type: string }>(`/plugins/detect?url=${encodeURIComponent(url)}`),
  install: (req: InstallRequest) =>
    api.post<InstalledPluginOut>('/plugins/install', req),
  uninstall: (id: string) => api.delete(`/plugins/install/${id}`),
  listInstalled: () => api.get<InstalledListResponse>('/plugins/installed'),
}
```

- [ ] **Step 2: Run type check**

```bash
cd frontend
bun run type-check
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/plugins.ts
git commit -m "feat(frontend/api): add MarketSkillOut, InstalledPluginOut types and marketApi"
```

---

## Task 12: Create `InstallFromUrlModal.vue`

**Files:**
- Create: `frontend/src/components/InstallFromUrlModal.vue`

- [ ] **Step 1: Create the component**

```vue
<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    @click.self="$emit('close')"
  >
    <div class="w-full max-w-md rounded-xl bg-gray-900 p-6 shadow-xl">
      <h2 class="mb-4 text-lg font-semibold text-white">Install from URL</h2>

      <div class="mb-4">
        <label class="mb-1 block text-sm text-gray-400">URL or npx command</label>
        <input
          v-model="urlInput"
          type="text"
          class="w-full rounded-lg bg-gray-800 px-3 py-2 text-white placeholder-gray-500 outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="https://example.com/skill.md  or  npx @pkg/server"
          @input="onInputChange"
        />
        <div class="mt-1 h-5 text-sm">
          <span v-if="detecting" class="text-gray-400">Detecting…</span>
          <span v-else-if="detectedType" class="text-green-400">
            Detected as: {{ detectedType }} ✓
          </span>
          <span v-else-if="showManualSelector && urlInput" class="text-yellow-400">
            Cannot auto-detect — select type below
          </span>
        </div>
      </div>

      <div v-if="showManualSelector && urlInput" class="mb-4">
        <label class="mb-1 block text-sm text-gray-400">Plugin type</label>
        <select
          v-model="manualType"
          class="w-full rounded-lg bg-gray-800 px-3 py-2 text-white outline-none"
        >
          <option value="">-- choose --</option>
          <option value="mcp">MCP Server</option>
          <option value="skill_md">SKILL.md</option>
          <option value="python_plugin">Python Plugin</option>
        </select>
      </div>

      <div class="mb-6">
        <label class="mb-2 block text-sm text-gray-400">Install scope</label>
        <div class="flex gap-4">
          <label class="flex cursor-pointer items-center gap-2 text-white">
            <input v-model="scope" type="radio" value="personal" class="accent-blue-500" />
            Personal (just me)
          </label>
          <label
            class="flex items-center gap-2"
            :class="isAdmin ? 'cursor-pointer text-white' : 'cursor-not-allowed text-gray-500'"
            :title="isAdmin ? '' : 'Admin required for system-wide installs'"
          >
            <input
              v-model="scope"
              type="radio"
              value="system"
              :disabled="!isAdmin"
              class="accent-blue-500"
            />
            System-wide
          </label>
        </div>
      </div>

      <div class="flex justify-end gap-3">
        <button
          class="rounded-lg px-4 py-2 text-gray-400 hover:text-white"
          @click="$emit('close')"
        >
          Cancel
        </button>
        <button
          class="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
          :disabled="!canInstall || installing"
          @click="doInstall"
        >
          {{ installing ? 'Installing…' : 'Install' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { marketApi } from '@/api/plugins'
import type { InstallRequest } from '@/api/plugins'

const emit = defineEmits<{
  close: []
  installed: [pluginId: string]
}>()

const auth = useAuthStore()
const isAdmin = computed(
  () => auth.user?.role === 'admin' || auth.user?.role === 'superadmin',
)

const urlInput = ref('')
const scope = ref<'personal' | 'system'>('personal')
const detectedType = ref<string | null>(null)
const showManualSelector = ref(false)
const manualType = ref('')
const detecting = ref(false)
const installing = ref(false)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function onInputChange() {
  detectedType.value = null
  showManualSelector.value = false
  manualType.value = ''
  if (!urlInput.value.trim()) return
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(runDetect, 500)
}

async function runDetect() {
  detecting.value = true
  try {
    const { data } = await marketApi.detect(urlInput.value.trim())
    detectedType.value = data.type
    showManualSelector.value = false
  } catch {
    detectedType.value = null
    showManualSelector.value = true
  } finally {
    detecting.value = false
  }
}

const resolvedType = computed(() => detectedType.value || manualType.value || null)
const canInstall = computed(() => Boolean(urlInput.value.trim() && resolvedType.value))

async function doInstall() {
  if (!canInstall.value || !resolvedType.value) return
  installing.value = true
  try {
    const req: InstallRequest = {
      url: urlInput.value.trim(),
      type: resolvedType.value as InstallRequest['type'],
      scope: scope.value,
    }
    const { data } = await marketApi.install(req)
    emit('installed', data.plugin_id)
    emit('close')
  } catch (err: unknown) {
    const detail = (err as any)?.response?.data?.detail
    alert(typeof detail === 'string' ? detail : 'Install failed')
  } finally {
    installing.value = false
  }
}
</script>
```

- [ ] **Step 2: Run type check**

```bash
cd frontend
bun run type-check
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/InstallFromUrlModal.vue
git commit -m "feat(frontend): add InstallFromUrlModal component"
```

---

## Task 13: Update `SkillMarketPage.vue`

**Files:**
- Modify: `frontend/src/pages/SkillMarketPage.vue`

Changes needed:
1. Remove `Skill` interface, import `MarketSkillOut` and `marketApi` from `@/api/plugins`
2. Replace `skill.version` / `skill.md_url` references
3. Replace old install call with `marketApi.install()`
4. Add category filter tabs
5. Add "Install from URL" button + `InstallFromUrlModal`

- [ ] **Step 1: Update imports and types**

Remove the local `Skill` interface and replace with:

```typescript
import { marketApi } from '@/api/plugins'
import type { MarketSkillOut } from '@/api/plugins'
import InstallFromUrlModal from '@/components/InstallFromUrlModal.vue'
import { useAuthStore } from '@/stores/auth'
```

Change `skills` ref type to `MarketSkillOut[]`. Update `loadSkills` to call `marketApi.listSkills()`.

- [ ] **Step 2: Update the install handler**

```typescript
const auth = useAuthStore()
const isAdmin = computed(
  () => auth.user?.role === 'admin' || auth.user?.role === 'superadmin',
)

async function installSkill(skill: MarketSkillOut, scope: 'personal' | 'system') {
  installingId.value = skill.id + '-' + scope
  try {
    await marketApi.install({ url: skill.install_url, type: skill.type, scope })
    await loadSkills()
  } catch (err: unknown) {
    console.error('Install failed', err)
  } finally {
    installingId.value = null
  }
}
```

- [ ] **Step 3: Add category filter**

```typescript
const activeCategory = ref<'all' | 'mcp' | 'skill_md' | 'python_plugin'>('all')

const filteredSkills = computed(() =>
  activeCategory.value === 'all'
    ? skills.value
    : skills.value.filter((s) => s.type === activeCategory.value),
)
```

- [ ] **Step 4: Update template**

Add filter tabs above the skill grid:

```html
<div class="mb-4 flex gap-2">
  <button
    v-for="[key, label] in [['all','All'],['mcp','MCP'],['skill_md','Skill'],['python_plugin','Plugin']]"
    :key="key"
    class="rounded-full px-3 py-1 text-sm transition"
    :class="activeCategory === key ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'"
    @click="activeCategory = key as typeof activeCategory.value"
  >{{ label }}</button>
</div>
```

Add "Install from URL" button near the page header:

```html
<button
  class="rounded-lg bg-purple-600 px-3 py-1.5 text-sm text-white hover:bg-purple-700"
  @click="showInstallModal = true"
>
  + Install from URL
</button>

<InstallFromUrlModal
  v-if="showInstallModal"
  @close="showInstallModal = false"
  @installed="loadSkills"
/>
```

Update each skill card's install button(s):

```html
<!-- Replace old single install button with: -->
<button @click="installSkill(skill, 'personal')">Install for Me</button>
<button
  v-if="isAdmin"
  @click="installSkill(skill, 'system')"
>Install System-wide</button>
```

Remove all references to `skill.version` and `skill.md_url`.

- [ ] **Step 5: Run type check and lint**

```bash
cd frontend
bun run type-check
bun run lint:fix
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SkillMarketPage.vue
git commit -m "feat(frontend): update SkillMarketPage — new schema, category tabs, URL install"
```

---

## Task 14: Update `PluginsPage.vue`

**Files:**
- Modify: `frontend/src/pages/PluginsPage.vue`

**Important:** The existing `GET /api/plugins` call (which shows the global in-memory plugin registry) must be **kept**. We add a new section below it showing `installed_plugins` from the DB. Do not remove the existing `pluginsApi.list()` call.

- [ ] **Step 1: Add import and data**

Add to imports:

```typescript
import { marketApi } from '@/api/plugins'
import type { InstalledPluginOut } from '@/api/plugins'
```

Add reactive data alongside existing data:

```typescript
const systemInstalled = ref<InstalledPluginOut[]>([])
const personalInstalled = ref<InstalledPluginOut[]>([])

async function loadInstalled() {
  const { data } = await marketApi.listInstalled()
  systemInstalled.value = data.system
  personalInstalled.value = data.personal
}
```

Call `loadInstalled()` in `onMounted` alongside the existing plugin list load.

- [ ] **Step 2: Add uninstall handler**

```typescript
async function uninstallInstalledPlugin(id: string) {
  if (!confirm('Uninstall this plugin?')) return
  await marketApi.uninstall(id)
  await loadInstalled()
}
```

- [ ] **Step 3: Add new sections to template**

Below the existing plugin list, add:

```html
<!-- System Installed Plugins (from DB) -->
<section v-if="systemInstalled.length || isAdmin" class="mt-8">
  <h2 class="mb-3 text-base font-semibold text-white">System Installed</h2>
  <div v-if="systemInstalled.length === 0" class="text-sm text-gray-500">None</div>
  <div
    v-for="p in systemInstalled"
    :key="p.id"
    class="mb-2 flex items-center justify-between rounded-lg bg-gray-800 px-4 py-3"
  >
    <div>
      <span class="mr-2 rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-300">{{ p.type }}</span>
      <span class="text-white">{{ p.name }}</span>
    </div>
    <button
      v-if="isAdmin"
      class="text-xs text-red-400 hover:text-red-300"
      @click="uninstallInstalledPlugin(p.id)"
    >Uninstall</button>
  </div>
</section>

<!-- Personal Installed Plugins (from DB) -->
<section class="mt-6">
  <h2 class="mb-3 text-base font-semibold text-white">My Installed Plugins</h2>
  <div v-if="personalInstalled.length === 0" class="text-sm text-gray-500">None</div>
  <div
    v-for="p in personalInstalled"
    :key="p.id"
    class="mb-2 flex items-center justify-between rounded-lg bg-gray-800 px-4 py-3"
  >
    <div>
      <span class="mr-2 rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-300">{{ p.type }}</span>
      <span class="text-white">{{ p.name }}</span>
    </div>
    <button
      class="text-xs text-red-400 hover:text-red-300"
      @click="uninstallInstalledPlugin(p.id)"
    >Uninstall</button>
  </div>
</section>
```

- [ ] **Step 4: Run type check and lint**

```bash
cd frontend
bun run type-check
bun run lint:fix
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PluginsPage.vue
git commit -m "feat(frontend): add system/personal installed sections to PluginsPage"
```

---

## Task 15: Smoke test

- [ ] **Step 1: Start the full stack**

```bash
docker compose up -d
docker compose ps
```

Expected: all containers show `healthy` or `running`, none show `unhealthy` or `exit`.

- [ ] **Step 2: Get an auth token**

```bash
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@jarvis.dev","password":"your-password"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token obtained: ${TOKEN:0:20}..."
```

- [ ] **Step 3: Verify Skill Market returns registry data**

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://localhost/api/plugins/market/skills | python3 -m json.tool | head -20
```

Expected: JSON array with `id`, `type`, `install_url` fields; no `md_url` or `version` fields; first entry is `mcp-github`.

- [ ] **Step 4: Test auto-detect endpoint**

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/plugins/detect?url=npx+%40modelcontextprotocol%2Fserver-github"
```

Expected: `{"type":"mcp"}`

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/plugins/detect?url=https%3A%2F%2Fexample.com%2Fweather.md"
```

Expected: `{"type":"skill_md"}`

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/plugins/detect?url=https%3A%2F%2Fexample.com%2Fsomething"
```

Expected: HTTP 422 with `candidates` in response.

- [ ] **Step 5: Test install + list + uninstall**

```bash
# Install a personal MCP plugin
RESULT=$(curl -s -X POST http://localhost/api/plugins/install \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"url":"npx @modelcontextprotocol/server-github","scope":"personal"}')
echo "$RESULT" | python3 -m json.tool
PLUGIN_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Verify it appears in list
curl -s -H "Authorization: Bearer $TOKEN" http://localhost/api/plugins/installed | python3 -c "
import sys, json; d=json.load(sys.stdin)
print('system:', len(d['system']), 'personal:', len(d['personal']))
print('personal[0]:', d['personal'][0]['plugin_id'] if d['personal'] else 'none')
"

# Duplicate install → 409
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost/api/plugins/install \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"url":"npx @modelcontextprotocol/server-github","scope":"personal"}'
# Expected: 409

# Uninstall
curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  "http://localhost/api/plugins/install/$PLUGIN_ID" \
  -H "Authorization: Bearer $TOKEN"
# Expected: 204
```

- [ ] **Step 6: Run backend test suite**

```bash
cd backend
uv run pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass, no failures.

- [ ] **Step 7: Commit any fixes from smoke test**

```bash
git add -p
git commit -m "fix: address issues found during smoke test"
```

---

## Task 16: Push to dev

- [ ] **Step 1: Run pre-commit hooks**

```bash
pre-commit run --all-files
```

Fix any issues and commit.

- [ ] **Step 2: Push**

```bash
git push origin dev
```
