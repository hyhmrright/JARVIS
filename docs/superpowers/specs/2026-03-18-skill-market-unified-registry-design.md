# Skill Market — Unified Registry & Community Install Design

**Date:** 2026-03-18
**Status:** Approved (rev 3)
**Scope:** Backend adapters, registry format, install pipeline, permission model, frontend UI

---

## Problem

JARVIS has a Skill Market UI and a plugin loader, but no working registry. The frontend shows an empty list because `skill_market_manager.fetch_registry()` returns nothing — there is no remote registry. Users also have no way to install skills discovered from community posts (Reddit, GitHub, Discord) without manually editing config files.

---

## Goal

1. A curated **Registry** (`registry/index.json` bundled in the JARVIS repo) that powers the Skill Market UI with real entries.
2. A **"Install from URL"** flow that accepts any community link, auto-detects its type, and installs it in one click.
3. **System-level** (admin installs for all users) and **personal-level** (user installs for themselves) scope, loaded per-request by the agent.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                  Skill Market UI                 │
│  ┌─────────────────┐  ┌───────────────────────┐ │
│  │  Curated Market  │  │  Install from URL     │ │
│  │  (browse+install)│  │  (auto-detect type)   │ │
│  └────────┬────────┘  └──────────┬────────────┘ │
└───────────┼──────────────────────┼───────────────┘
            ▼                      ▼
┌─────────────────────────────────────────────────┐
│              Backend Plugin Manager              │
│                                                  │
│  Type Detector ──→ MCP Adapter                  │
│                ──→ SKILL.md Adapter              │
│                ──→ Python Plugin Adapter         │
└──────────────────────────┬──────────────────────┘
                           ▼
              ┌────────────────────────┐
              │  installed_plugins DB  │
              │  system / personal     │
              └────────────────────────┘
```

All installs — whether from the curated Registry or a pasted URL — go through the same pipeline. The user experience is identical.

---

## Registry Format

File: `registry/index.json` — tracked in the JARVIS repository and **read from disk** at runtime. The backend does not fetch it over HTTP; `skill_market_manager.fetch_registry()` is rewritten to read this local file.

```json
{
  "version": "1",
  "skills": [
    {
      "id": "mcp-github",
      "name": "GitHub MCP Server",
      "description": "Read repos, issues, PRs via GitHub API",
      "type": "mcp",
      "source": "https://github.com/modelcontextprotocol/servers",
      "install_url": "npx @modelcontextprotocol/server-github",
      "author": "Anthropic",
      "tags": ["dev", "github"],
      "scope": ["system", "personal"]
    },
    {
      "id": "skill-weather",
      "name": "Weather Query",
      "description": "Get current weather for any city",
      "type": "skill_md",
      "install_url": "https://raw.githubusercontent.com/xxx/jarvis-skills/main/weather.md",
      "author": "community",
      "tags": ["utility"],
      "scope": ["system", "personal"]
    }
  ]
}
```

**Supported `type` values:** `mcp` | `skill_md` | `python_plugin`

> **Note:** `langchain` type is explicitly out of scope for this iteration. It requires defining a URL convention for LangChain tools that does not yet exist, and `python_plugin` already handles `.py` files that wrap LangChain tools.

Community members contribute by opening a PR to add entries to this file.

---

## Type Auto-Detection

When a user pastes a URL without specifying a type, the backend detects it:

| Input pattern | Detected type |
|---------------|---------------|
| URL ends with `.md` or contains `SKILL.md` | `skill_md` |
| URL ends with `.py` | `python_plugin` |
| URL ends with `.zip` or GitHub archive link | `python_plugin` |
| String starting with `npx ` | `mcp` |
| `mcp://` scheme | `mcp` |
| GitHub repo URL (no path or `/tree/` path) | Fetch `manifest.yaml`; if found → `python_plugin`; else → `skill_md` |
| Unrecognized | Return 422 with `{ "candidates": ["mcp","skill_md","python_plugin"] }` — frontend shows manual selector |

**Frontend auto-detect endpoint:**

```
GET /api/plugins/detect?url=<encoded-url>
Response 200: { "type": "skill_md" | "mcp" | "python_plugin" }
Response 422: { "detail": "Cannot determine type", "candidates": ["mcp","skill_md","python_plugin"] }
Auth: any authenticated user
```

The frontend calls this endpoint debounced (500ms) as the user types. Pattern-based detections (`.md`, `.py`, `npx`) resolve instantly in the handler without network I/O; only GitHub repo URLs trigger an outbound fetch inside the handler. The indicator shows a spinner during the network call and falls back to the manual selector on timeout (5s) or network error.

---

## plugin_id Derivation

`plugin_id` must be unique per installation target. Derivation rules per type:

| Type | Source | Derivation |
|------|--------|------------|
| Registry install (any type) | Registry JSON `"id"` field | Use as-is |
| `skill_md` (URL install) | URL filename stem | `Path(url.rstrip('/').split('?')[0]).stem` lowercased, e.g. `weather` |
| `python_plugin` (URL install) | URL filename stem | Same as above |
| `mcp` (npx install) | npm package name | Strip leading `@scope/` and normalize: `npx @modelcontextprotocol/server-github` → `mcp-server-github` |

`plugin_id` values must match between `installed_plugins` and `plugin_configs` tables (the existing per-user plugin configuration table uses the same `plugin_id` key). URL installs derive `plugin_id` from the URL/command using the rules above; registry installs use the registry's `"id"` field directly.

---

## Name Derivation for URL Installs

When a user installs via raw URL (no registry entry), the `name` field is derived as follows:

| Type | Source | Fallback |
|------|--------|---------|
| `skill_md` | `# Title` heading from downloaded Markdown (parsed by existing `skill_parser.parse_markdown()`) | filename stem, title-cased |
| `python_plugin` | `name` field from `manifest.yaml` if present | filename stem, title-cased |
| `mcp` (npx) | npm package name with scope stripped and title-cased: `server-github` → `Server Github` | raw command string |

---

## Install Pipeline

```
User clicks Install / pastes URL
        ↓
Frontend: POST /api/plugins/install
  { url: str, type?: "mcp"|"skill_md"|"python_plugin", scope: "system"|"personal" }
        ↓
Route dependency: get_current_user (any authenticated user)
Handler checks: if scope == "system" and not current_user.is_admin → raise 403
        ↓
Type detection (if type omitted) — same logic as GET /api/plugins/detect
        ↓
Derive plugin_id and name (see derivation rules above)
        ↓
Adapter dispatch:
  mcp          → parse npx command into mcp_command + mcp_args; no filesystem write
  skill_md     → download .md, validate it parses via skill_parser; save to scope path
  python_plugin → download .py/.zip, extract if zip; save to scope path
        ↓
Write to installed_plugins (duplicate → catch IntegrityError → 409)
        ↓
System installs: reload system plugins under asyncio.Lock (see Race Conditions)
Personal installs: no reload (per-request loading handles it)
        ↓
Return InstalledPluginOut
```

---

## Permission Model

| Action | System scope | Personal scope |
|--------|-------------|----------------|
| Install | Admin only | Any user |
| Uninstall | Admin only | Owner only |
| Visible to | All users | Owner only |

**Per-request tool loading** (in `_load_tools` / agent init):
1. Load system plugins from `{settings.installed_plugins_dir}/system/` + system MCP configs from DB
2. Load personal plugins for `current_user.id` from `{settings.installed_plugins_dir}/users/{user_id}/` + personal MCP configs from DB
3. Merge: personal plugin takes precedence over system plugin with the same name

This replaces the current global `plugin_registry.get_all_tools()` call for chat requests. The existing `UserSettings.plugin_permissions` RBAC table controls which system tools a user can use — this is unchanged. Personal plugins bypass the RBAC table (user always has permission to their own plugins).

**Storage paths** (resolved via `settings.installed_plugins_dir`, a new config key defaulting to `Path(settings.data_dir) / "installed_plugins"` — fully resolved at startup, no `~` in runtime paths):
- System filesystem: `{installed_plugins_dir}/system/`
- Personal filesystem: `{installed_plugins_dir}/users/{user_id}/`
- MCP configs: stored in `installed_plugins` table only, no filesystem write

**Workspace scope is explicitly out of scope** for this iteration. Workspace-level plugin management is deferred to a future release.

---

## Database

New table: `installed_plugins`

```sql
CREATE TABLE installed_plugins (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_id    TEXT NOT NULL,
    name         TEXT NOT NULL,
    type         TEXT NOT NULL CHECK (type IN ('mcp', 'skill_md', 'python_plugin')),
    install_url  TEXT NOT NULL,
    mcp_command  TEXT,                   -- for type=mcp: e.g. "npx"
    mcp_args     JSONB,                  -- for type=mcp: e.g. ["@modelcontextprotocol/server-github"]
    scope        TEXT NOT NULL CHECK (scope IN ('system', 'personal')),
    installed_by UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- Personal installs: enforce uniqueness per user
CREATE UNIQUE INDEX installed_plugins_personal_unique
    ON installed_plugins (plugin_id, installed_by)
    WHERE scope = 'personal';

-- System installs: enforce uniqueness globally (installed_by IS NULL)
CREATE UNIQUE INDEX installed_plugins_system_unique
    ON installed_plugins (plugin_id)
    WHERE scope = 'system';

-- Lookup index for per-request tool loading
CREATE INDEX installed_plugins_scope_user
    ON installed_plugins (scope, installed_by);
```

`installed_by` is NULL for system-scope installs (admin action on behalf of the system). The separate partial indexes handle the NULL-semantics limitation of standard UNIQUE constraints.

---

## API Schemas

### MarketSkillOut (replaces existing `MarketSkill` model)

```python
class MarketSkillOut(BaseModel):
    id: str
    name: str
    description: str
    type: Literal["mcp", "skill_md", "python_plugin"]
    install_url: str
    source: str | None = None     # human-readable source link
    author: str
    tags: list[str]
    scope: list[Literal["system", "personal"]]
```

Replaces old fields `version` and `md_url`. The frontend `SkillMarketPage.vue` and its TypeScript `Skill` interface must be updated to remove `md_url`/`version` and add `type`/`install_url`/`tags`.

### InstalledPluginOut (new, used by install + list endpoints)

```python
class InstalledPluginOut(BaseModel):
    id: str           # installed_plugins.id (UUID)
    plugin_id: str    # e.g. "mcp-github"
    name: str
    type: Literal["mcp", "skill_md", "python_plugin"]
    install_url: str
    scope: Literal["system", "personal"]
    installed_by: str | None   # user UUID; None for system installs
    created_at: datetime
```

---

## API Changes

### Endpoints replaced

| Old endpoint | Replacement |
|---|---|
| `POST /api/plugins/market/install/{skill_id}` | `POST /api/plugins/install` |
| `DELETE /api/plugins/market/uninstall/{skill_id}` | `DELETE /api/plugins/install/{installed_plugin_id}` |

The existing `GET /api/plugins` (returns in-memory global registry as `list[PluginInfo]`) is **kept unchanged** — it shows globally loaded SDK plugins and is used by the admin panel. It is not replaced.

### New / updated endpoints

**Detect type (new):**
```
GET /api/plugins/detect?url={encoded_url}
Response 200: { "type": "skill_md" | "mcp" | "python_plugin" }
Response 422: { "detail": "Cannot determine type", "candidates": [...] }
Auth: any authenticated user (get_current_user)
```

**Market skills (updated response schema):**
```
GET /api/plugins/market/skills
Response 200: list[MarketSkillOut]
Auth: any authenticated user
```
Handler rewrites `fetch_registry()` to read `registry/index.json` from disk and return `list[MarketSkillOut]`. Old `version` and `md_url` fields are removed.

**Install (new):**
```
POST /api/plugins/install
Body: { url: str, type?: str, scope: "system" | "personal" }
Response 200: InstalledPluginOut
Response 403: scope=system requested by non-admin
Response 409: { "detail": "Already installed" }
Response 422: { "detail": "reason" } or { "detail": "...", "candidates": [...] }
Auth: get_current_user; handler raises 403 if scope=system and not is_admin
```

**Uninstall (new):**
```
DELETE /api/plugins/install/{installed_plugin_id}
Response 204: no content
Response 403: not admin (system) or not owner (personal)
Response 404: not found
Auth: get_current_user; handler checks scope+ownership
Action: delete DB row; if skill_md or python_plugin, also delete the filesystem file
```

**List installed (updated):**
```
GET /api/plugins/installed
Response 200: { "system": list[InstalledPluginOut], "personal": list[InstalledPluginOut] }
Auth: get_current_user
Behavior: system list always returned; personal list filtered to current_user.id
```

---

## Race Conditions — System Install Reload

System installs trigger a reload of the shared plugin registry. The reload sequence is protected by a module-level `asyncio.Lock` in `app/plugins/loader.py`:

```python
_system_reload_lock = asyncio.Lock()

async def reload_system_plugins() -> None:
    async with _system_reload_lock:
        plugin_registry.deactivate_all()
        plugin_registry.clear()
        await load_all_plugins()  # reads from installed_plugins_dir/system/
        plugin_registry.activate_all()
```

Personal installs do not call this function — their plugins are loaded per-request from the DB + filesystem on each chat request.

---

## Backward Compatibility

- **`GET /api/plugins`** (global registry view, `list[PluginInfo]`): kept as-is. This endpoint reflects the in-memory `PluginRegistry` loaded at startup from SDK plugins. It is not affected by this change.
- **`plugin_configs` table**: keyed by `plugin_id`. After migration, `plugin_id` values in `installed_plugins` follow the derivation rules above. Registry install IDs (e.g. `"mcp-github"`) should match what was previously used in `plugin_configs`; URL install IDs are newly derived and will have no prior `plugin_configs` rows.
- **Existing `POST /api/plugins/market/install/{skill_id}`**: removed. Any existing calls (internal or from the existing frontend button) must be updated to use the new `POST /api/plugins/install`.

---

## Backend File Changes

| File | Change |
|------|--------|
| `registry/index.json` | New — curated skill registry |
| `app/core/config.py` | Add `installed_plugins_dir: Path` setting |
| `app/services/skill_market.py` | Replace HTTP fetch with local file read; update `MarketSkillOut` schema |
| `app/plugins/type_detector.py` | New — URL → type + plugin_id + name derivation |
| `app/plugins/adapters/mcp.py` | New — parses npx command, stores to DB |
| `app/plugins/adapters/skill_md.py` | New — replaces `SkillMarketManager.install_skill()` |
| `app/plugins/adapters/python_plugin.py` | New — extracts from existing `install_plugin_from_url` |
| `app/plugins/loader.py` | Add `_system_reload_lock`; add `reload_system_plugins()` |
| `app/api/plugins.py` | Add detect/install/uninstall endpoints; update market/skills; update installed |
| `app/api/chat.py` | Update `_load_tools` to do per-request system+personal merge from DB + filesystem |
| `alembic/versions/xxx_add_installed_plugins.py` | New migration |

---

## Frontend Changes

### `SkillMarketPage.vue`
- Update `Skill` TypeScript interface: remove `md_url`, `version`; add `type`, `install_url`, `tags`
- Load registry from `GET /api/plugins/market/skills`
- Add category filter tabs: All / MCP / Skill / Plugin (filter by `type`)
- Each card: **Install for Me** button (all users) + **Install System-wide** button (admin only, greyed out otherwise)
- Add **「+ Install from URL」** button → opens `InstallFromUrlModal`

### `InstallFromUrlModal.vue` (new component)
1. Paste/type input field
2. Live auto-detect: calls `GET /api/plugins/detect?url=...` debounced 500ms; shows spinner → "Detected as: SKILL.md ✓" or manual type selector on 422
3. Scope selector: ○ Personal  ● System (System disabled + tooltip for non-admin)
4. Confirm → `POST /api/plugins/install` → close modal, show toast

### `PluginsPage.vue`
- Remove call to `GET /api/plugins` (old global registry view)
- Split into two sections: **System Plugins** (admin can uninstall) / **My Plugins** (owner can uninstall)
- Each entry shows type badge: `MCP` / `Skill` / `Plugin`
- Load from `GET /api/plugins/installed`

---

## Error Handling

| Scenario | HTTP | Response |
|----------|------|----------|
| URL unreachable / timeout | 400 | `{ "detail": "Could not fetch URL" }` |
| Type undetectable | 422 | `{ "detail": "Cannot determine type", "candidates": ["mcp","skill_md","python_plugin"] }` |
| Install fails (bad format / parse error) | 422 | `{ "detail": "reason" }` — nothing written to DB |
| Duplicate install | 409 | `{ "detail": "Already installed" }` |
| Non-admin requests system scope | 403 | `{ "detail": "Admin required for system scope" }` |
| Uninstall by non-owner / non-admin | 403 | `{ "detail": "Forbidden" }` |
| Installed plugin not found | 404 | `{ "detail": "Not found" }` |

---

## Out of Scope

- Workspace-level plugin scope (deferred)
- Skill ratings / reviews
- Versioning / upgrade flow (install always gets latest)
- LangChain tool type (deferred — no URL convention defined)
- Publishing skills to the registry from within JARVIS UI (community contributes via GitHub PR)
- Sandboxed loading of untrusted Python plugins (existing sandbox handles code execution; plugin loading is trusted)
