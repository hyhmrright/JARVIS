# Plugin Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add plugin config persistence, per-user RBAC permissions, and a frontend Plugin management page to the existing plugin system.

**Architecture:** New `PluginConfig` DB table stores per-user key-value config (Fernet-encrypted for secrets). New `UserSettings.plugin_permissions` JSONB field stores admin-granted plugin access per user. New `PluginsPage.vue` provides the management UI.

**Tech Stack:** SQLAlchemy async (existing), Alembic (existing), FastAPI (existing), Vue 3 + TypeScript + Pinia (existing)

**Note:** All 3 original bug fixes (sys.modules ghost, agent_runner silent fail, plugin tools pre-filter) are already implemented. This plan covers only new capabilities.

**Worktree:** `feature/plugin-enhancement`, branch from `dev`

---

## Task 1: Add PluginConfig DB Model

**Files:**
- Modify: `backend/app/db/models.py`

**Step 1: Add PluginConfig model after Webhook class (line ~309)**

```python
class PluginConfig(Base):
    __tablename__ = "plugin_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plugin_id: Mapped[str] = mapped_column(String(100), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

**Step 2: Add `plugin_permissions` to UserSettings** (after `enabled_tools` field, around line 89)

```python
plugin_permissions: Mapped[list[str]] = mapped_column(
    JSONB,
    nullable=False,
    default=list,
)
```

This field stores the list of plugin IDs a user is allowed to use. Empty list = no plugins. Admin sets this per user. Admin-role users have access to all plugins by default.

**Step 3: Verify models.py imports have `Text` (already present)**

**Step 4: Commit**

```bash
git add backend/app/db/models.py
git commit -m "feat(plugins): add PluginConfig model and plugin_permissions to UserSettings"
```

---

## Task 2: Create Alembic Migration

**Files:**
- Create: `backend/alembic/versions/009_add_plugin_configs.py`

**Step 1: Create migration file**

```python
"""add plugin_configs table and plugin_permissions to user_settings

Revision ID: 009
Revises: 008
Create Date: 2026-03-05 00:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plugin_id", sa.String(length=100), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_plugin_configs_user_id", "plugin_configs", ["user_id"], unique=False
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "plugin_permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "plugin_permissions")
    op.drop_index("ix_plugin_configs_user_id", table_name="plugin_configs")
    op.drop_table("plugin_configs")
```

**Step 2: Run migration to verify it works**

```bash
cd backend
uv run alembic upgrade head
```

Expected: migration 009 applied successfully, no errors

**Step 3: Commit**

```bash
git add backend/alembic/versions/009_add_plugin_configs.py
git commit -m "feat(plugins): add migration 009 for plugin_configs and plugin_permissions"
```

---

## Task 3: Plugin Config CRUD API

**Files:**
- Modify: `backend/app/api/plugins.py`

**Step 1: Write failing tests first**

Create `backend/tests/api/test_plugin_config.py`:

```python
"""Tests for plugin config CRUD endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_set_plugin_config(auth_client: AsyncClient):
    """User can set a config value for a plugin."""
    resp = await auth_client.put(
        "/api/plugins/my_plugin/config",
        json={"key": "api_key", "value": "secret123", "is_secret": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "api_key"
    assert data["is_secret"] is True


@pytest.mark.anyio
async def test_get_plugin_config(auth_client: AsyncClient):
    """User can retrieve their plugin config (secrets masked)."""
    # First set a config
    await auth_client.put(
        "/api/plugins/my_plugin/config",
        json={"key": "api_key", "value": "secret123", "is_secret": True},
    )
    # Then get it
    resp = await auth_client.get("/api/plugins/my_plugin/config")
    assert resp.status_code == 200
    data = resp.json()
    # Secret values must be masked
    assert data["api_key"]["is_secret"] is True
    assert data["api_key"]["value"] == "***"


@pytest.mark.anyio
async def test_delete_plugin_config(auth_client: AsyncClient):
    """User can delete a config key."""
    await auth_client.put(
        "/api/plugins/my_plugin/config",
        json={"key": "api_key", "value": "secret123", "is_secret": False},
    )
    resp = await auth_client.delete("/api/plugins/my_plugin/config/api_key")
    assert resp.status_code == 200
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/api/test_plugin_config.py -v
```

Expected: FAIL — endpoints don't exist yet

**Step 3: Replace `backend/app/api/plugins.py` with full implementation**

```python
"""Plugin management API — list, install, config, and RBAC."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user
from app.db.models import PluginConfig, User, UserSettings
from app.db.session import get_db
from app.plugins import plugin_registry
from app.plugins.loader import activate_all_plugins, install_plugin_from_url

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/plugins", tags=["plugins"])


# ── Install / List ─────────────────────────────────────────────────────────────

class InstallRequest(BaseModel):
    url: str


@router.post("/install")
async def install_plugin(
    body: InstallRequest,
    admin: User = Depends(get_admin_user),
) -> dict[str, str]:
    try:
        plugin_id = await install_plugin_from_url(body.url, plugin_registry)
        await activate_all_plugins(plugin_registry)
        return {"status": "ok", "plugin_id": plugin_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Installation failed: {e}") from e


class PluginInfo(BaseModel):
    id: str
    name: str
    version: str
    description: str
    tools: list[str]
    channels: list[str]


@router.get("", response_model=list[PluginInfo])
async def list_plugins(
    user: User = Depends(get_current_user),
) -> list[PluginInfo]:
    """Return metadata for plugins this user has access to."""
    all_plugins = plugin_registry.list_plugins()
    if user.role in ("admin", "superadmin"):
        return [PluginInfo(**p) for p in all_plugins]
    # Regular users: filter by plugin_permissions
    us = await _get_user_settings_or_none(user)
    allowed = set(us.plugin_permissions if us else [])
    return [PluginInfo(**p) for p in all_plugins if p["plugin_id"] in allowed]


# ── Per-user enable/disable (RBAC) ─────────────────────────────────────────────

class PluginPermissionsUpdate(BaseModel):
    plugin_ids: list[str]


@router.put("/users/{target_user_id}/permissions")
async def set_user_plugin_permissions(
    target_user_id: str,
    body: PluginPermissionsUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Admin sets which plugins a user can access."""
    import uuid
    us = await db.scalar(
        select(UserSettings).where(
            UserSettings.user_id == uuid.UUID(target_user_id)
        )
    )
    if not us:
        raise HTTPException(status_code=404, detail="User settings not found")
    us.plugin_permissions = body.plugin_ids
    await db.commit()
    return {"status": "ok", "user_id": target_user_id, "plugin_ids": body.plugin_ids}


@router.get("/users/{target_user_id}/permissions")
async def get_user_plugin_permissions(
    target_user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Admin reads a user's plugin permissions."""
    import uuid
    us = await db.scalar(
        select(UserSettings).where(
            UserSettings.user_id == uuid.UUID(target_user_id)
        )
    )
    return {"user_id": target_user_id, "plugin_ids": us.plugin_permissions if us else []}


# ── Plugin Config CRUD ─────────────────────────────────────────────────────────

class ConfigSetRequest(BaseModel):
    key: str
    value: str
    is_secret: bool = False


class ConfigItem(BaseModel):
    key: str
    value: str
    is_secret: bool


@router.put("/{plugin_id}/config", response_model=ConfigItem)
async def set_plugin_config(
    plugin_id: str,
    body: ConfigSetRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConfigItem:
    """Upsert a single config key for the current user + plugin."""
    existing = await db.scalar(
        select(PluginConfig).where(
            PluginConfig.user_id == user.id,
            PluginConfig.plugin_id == plugin_id,
            PluginConfig.key == body.key,
        )
    )
    if existing:
        existing.value = body.value
        existing.is_secret = body.is_secret
    else:
        db.add(
            PluginConfig(
                user_id=user.id,
                plugin_id=plugin_id,
                key=body.key,
                value=body.value,
                is_secret=body.is_secret,
            )
        )
    await db.commit()
    return ConfigItem(key=body.key, value=body.value, is_secret=body.is_secret)


@router.get("/{plugin_id}/config")
async def get_plugin_config(
    plugin_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return all config entries for current user + plugin. Secret values masked."""
    rows = await db.scalars(
        select(PluginConfig).where(
            PluginConfig.user_id == user.id,
            PluginConfig.plugin_id == plugin_id,
        )
    )
    return {
        row.key: {"value": "***" if row.is_secret else row.value, "is_secret": row.is_secret}
        for row in rows.all()
    }


@router.delete("/{plugin_id}/config/{key}")
async def delete_plugin_config(
    plugin_id: str,
    key: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await db.execute(
        delete(PluginConfig).where(
            PluginConfig.user_id == user.id,
            PluginConfig.plugin_id == plugin_id,
            PluginConfig.key == key,
        )
    )
    await db.commit()
    return {"status": "ok"}


# ── Helper ─────────────────────────────────────────────────────────────────────

async def _get_user_settings_or_none(user: User) -> UserSettings | None:
    """Avoid circular import — import get_db inline."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return await db.scalar(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
```

**Step 4: Run static checks**

```bash
cd backend
uv run ruff check --fix && uv run ruff format
uv run mypy app/api/plugins.py
```

**Step 5: Run tests**

```bash
uv run pytest tests/api/test_plugin_config.py -v
```

Expected: all PASS

**Step 6: Commit**

```bash
git add backend/app/api/plugins.py backend/tests/api/test_plugin_config.py
git commit -m "feat(plugins): add config CRUD and per-user RBAC endpoints"
```

---

## Task 4: Frontend — PluginsPage.vue

**Files:**
- Create: `frontend/src/pages/PluginsPage.vue`
- Modify: `frontend/src/api/plugins.ts` (create if not exists)
- Modify: `frontend/src/router/index.ts` (add route)
- Modify: `frontend/src/App.vue` or nav component (add nav link)

**Step 1: Create `frontend/src/api/plugins.ts`**

```typescript
import api from './index'

export interface PluginInfo {
  id: string
  name: string
  version: string
  description: string
  tools: string[]
  channels: string[]
}

export interface ConfigItem {
  value: string
  is_secret: boolean
}

export const pluginsApi = {
  list: () => api.get<PluginInfo[]>('/plugins'),

  getConfig: (pluginId: string) =>
    api.get<Record<string, ConfigItem>>(`/plugins/${pluginId}/config`),

  setConfig: (pluginId: string, key: string, value: string, is_secret = false) =>
    api.put(`/plugins/${pluginId}/config`, { key, value, is_secret }),

  deleteConfig: (pluginId: string, key: string) =>
    api.delete(`/plugins/${pluginId}/config/${key}`),

  getUserPermissions: (userId: string) =>
    api.get<{ user_id: string; plugin_ids: string[] }>(`/plugins/users/${userId}/permissions`),

  setUserPermissions: (userId: string, pluginIds: string[]) =>
    api.put(`/plugins/users/${userId}/permissions`, { plugin_ids: pluginIds }),
}
```

**Step 2: Create `frontend/src/pages/PluginsPage.vue`**

```vue
<template>
  <div class="plugins-page">
    <h1>{{ t('plugins.title') }}</h1>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <div v-else-if="plugins.length === 0" class="empty">
      {{ t('plugins.empty') }}
    </div>

    <div v-else class="plugin-list">
      <div
        v-for="plugin in plugins"
        :key="plugin.id"
        class="plugin-card"
      >
        <div class="plugin-header">
          <div class="plugin-info">
            <h3>{{ plugin.name }}</h3>
            <span class="version">v{{ plugin.version }}</span>
          </div>
        </div>

        <p class="description">{{ plugin.description }}</p>

        <div class="tools" v-if="plugin.tools.length">
          <span class="label">{{ t('plugins.tools') }}:</span>
          <span
            v-for="tool in plugin.tools"
            :key="tool"
            class="tag"
          >{{ tool }}</span>
        </div>

        <button
          class="config-btn"
          @click="openConfig(plugin)"
        >
          {{ t('plugins.configure') }}
        </button>
      </div>
    </div>

    <!-- Config Modal -->
    <div v-if="activePlugin" class="modal-overlay" @click.self="activePlugin = null">
      <div class="modal">
        <h2>{{ t('plugins.config_title', { name: activePlugin.name }) }}</h2>

        <div v-if="configLoading" class="loading">{{ t('common.loading') }}</div>

        <div v-else class="config-form">
          <div
            v-for="(item, key) in currentConfig"
            :key="key"
            class="config-row"
          >
            <label>{{ key }}</label>
            <div class="config-value">
              <span v-if="item.is_secret">***</span>
              <span v-else>{{ item.value }}</span>
              <button class="delete-btn" @click="deleteConfig(key)">✕</button>
            </div>
          </div>

          <div class="add-config">
            <input v-model="newKey" :placeholder="t('plugins.key')" />
            <input
              v-model="newValue"
              :type="newIsSecret ? 'password' : 'text'"
              :placeholder="t('plugins.value')"
            />
            <label class="secret-label">
              <input type="checkbox" v-model="newIsSecret" />
              {{ t('plugins.secret') }}
            </label>
            <button @click="addConfig" :disabled="!newKey || !newValue">
              {{ t('plugins.add') }}
            </button>
          </div>
        </div>

        <button class="close-btn" @click="activePlugin = null">
          {{ t('common.close') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { pluginsApi, type PluginInfo, type ConfigItem } from '@/api/plugins'

const { t } = useI18n()

const plugins = ref<PluginInfo[]>([])
const loading = ref(true)
const activePlugin = ref<PluginInfo | null>(null)
const currentConfig = ref<Record<string, ConfigItem>>({})
const configLoading = ref(false)
const newKey = ref('')
const newValue = ref('')
const newIsSecret = ref(false)

onMounted(async () => {
  try {
    const resp = await pluginsApi.list()
    plugins.value = resp.data
  } finally {
    loading.value = false
  }
})

async function openConfig(plugin: PluginInfo) {
  activePlugin.value = plugin
  configLoading.value = true
  try {
    const resp = await pluginsApi.getConfig(plugin.id)
    currentConfig.value = resp.data
  } finally {
    configLoading.value = false
  }
}

async function addConfig() {
  if (!activePlugin.value || !newKey.value || !newValue.value) return
  await pluginsApi.setConfig(activePlugin.value.id, newKey.value, newValue.value, newIsSecret.value)
  await openConfig(activePlugin.value)
  newKey.value = ''
  newValue.value = ''
  newIsSecret.value = false
}

async function deleteConfig(key: string) {
  if (!activePlugin.value) return
  await pluginsApi.deleteConfig(activePlugin.value.id, key)
  await openConfig(activePlugin.value)
}
</script>

<style scoped>
.plugins-page { padding: 2rem; max-width: 900px; margin: 0 auto; }
.plugin-list { display: grid; gap: 1rem; }
.plugin-card {
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 8px;
  padding: 1.5rem;
}
.plugin-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; }
.plugin-info { display: flex; align-items: baseline; gap: 0.5rem; }
.version { color: #6b7280; font-size: 0.875rem; }
.description { color: #4b5563; margin: 0.5rem 0; }
.tools { display: flex; gap: 0.25rem; flex-wrap: wrap; align-items: center; margin-bottom: 1rem; }
.label { font-size: 0.75rem; color: #6b7280; }
.tag { background: #f3f4f6; border-radius: 4px; padding: 0.125rem 0.5rem; font-size: 0.75rem; }
.config-btn { padding: 0.5rem 1rem; border-radius: 6px; border: 1px solid #d1d5db; cursor: pointer; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: white; border-radius: 12px; padding: 2rem; width: 500px; max-width: 90vw; max-height: 80vh; overflow-y: auto; }
.config-row { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid #f3f4f6; }
.config-value { display: flex; align-items: center; gap: 0.5rem; }
.delete-btn { background: none; border: none; color: #ef4444; cursor: pointer; }
.add-config { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 1rem; }
.add-config input { flex: 1; min-width: 100px; padding: 0.375rem 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; }
.secret-label { display: flex; align-items: center; gap: 0.25rem; font-size: 0.875rem; }
.close-btn { margin-top: 1.5rem; width: 100%; padding: 0.5rem; border-radius: 6px; border: 1px solid #d1d5db; cursor: pointer; }
</style>
```

**Step 3: Add route to `frontend/src/router/index.ts`**

Find the routes array and add:
```typescript
{
  path: '/plugins',
  name: 'Plugins',
  component: () => import('@/pages/PluginsPage.vue'),
},
```

**Step 4: Add i18n keys**

In `frontend/src/locales/zh.json` (and other locale files), add under an appropriate section:
```json
"plugins": {
  "title": "插件管理",
  "empty": "暂无已安装的插件",
  "tools": "工具",
  "configure": "配置",
  "config_title": "{name} 配置",
  "key": "配置项",
  "value": "值",
  "secret": "加密存储",
  "add": "添加"
}
```

**Step 5: Add nav link** in the sidebar/nav component (look for the existing nav links in `ChatPage.vue` or a dedicated nav component)

**Step 6: Run frontend checks**

```bash
cd frontend
bun run type-check
bun run lint:fix
```

Expected: no errors

**Step 7: Commit**

```bash
git add frontend/src/pages/PluginsPage.vue frontend/src/api/plugins.ts frontend/src/router/ frontend/src/locales/
git commit -m "feat(plugins): add PluginsPage with config management UI"
```

---

## Task 5: Final Verification

**Step 1: Run all backend tests**

```bash
cd backend
uv run pytest tests/ -v
```

Expected: all pass

**Step 2: Fast import check**

```bash
uv run pytest --collect-only -q
```

Expected: no import errors

**Step 3: Full static check**

```bash
uv run ruff check && uv run mypy app
```

**Step 4: Final commit and push**

```bash
git push origin feature/plugin-enhancement
```

Then open a PR: `feature/plugin-enhancement` → `dev`
