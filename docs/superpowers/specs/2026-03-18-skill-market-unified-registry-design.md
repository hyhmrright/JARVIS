# Skill Market — Unified Registry & Community Install Design

**Date:** 2026-03-18
**Status:** Approved
**Scope:** Backend adapters, registry format, install pipeline, permission model, frontend UI

---

## Problem

JARVIS has a Skill Market UI and a plugin loader, but no working registry. The frontend shows an empty list because `skill_market_manager.fetch_registry()` returns nothing — there is no remote registry. Users also have no way to install skills discovered from community posts (Reddit, GitHub, Discord) without manually editing config files.

---

## Goal

1. A curated **Registry** (`registry/index.json` in the JARVIS repo) that powers the Skill Market UI with real entries.
2. A **"Install from URL"** flow that accepts any community link, auto-detects its type, and installs it in one click.
3. **System-level** (admin installs for all users) and **personal-level** (user installs for themselves) scope, loaded in layers by the agent.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                  Skill Market UI                 │
│  ┌─────────────────┐  ┌───────────────────────┐ │
│  │  精选 Registry   │  │  粘贴 URL / 链接安装  │ │
│  │  (浏览+一键装)   │  │  (自动识别类型)       │ │
│  └────────┬────────┘  └──────────┬────────────┘ │
└───────────┼──────────────────────┼───────────────┘
            ▼                      ▼
┌─────────────────────────────────────────────────┐
│              Backend Plugin Manager              │
│                                                  │
│  Type Detector ──→ MCP Adapter                  │
│                ──→ SKILL.md Adapter              │
│                ──→ Python Plugin Adapter         │
│                ──→ LangChain Tool Adapter        │
└──────────────────────────┬──────────────────────┘
                           ▼
              ┌────────────────────────┐
              │  system scope (admin)  │
              │  personal scope (user) │
              └────────────────────────┘
```

Regardless of whether the source is the curated Registry or a community post URL, all installs go through the same pipeline. The user experience is identical — paste and install.

---

## Registry Format

File: `registry/index.json` (tracked in the JARVIS repository)

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

**Supported `type` values:** `mcp` | `skill_md` | `python_plugin` | `langchain`

The backend fetches this file at startup and caches it. Community members contribute by opening a PR to add entries.

---

## Type Auto-Detection

When a user pastes a URL without specifying a type, the backend detects it:

| Input pattern | Detected type |
|---------------|---------------|
| URL ends with `.md` or contains `SKILL.md` | `skill_md` |
| URL ends with `.py` | `python_plugin` |
| URL ends with `.zip` or GitHub archive link | `python_plugin` |
| `mcp://` scheme or URL contains `mcp-server` | `mcp` |
| `npx @modelcontextprotocol/...` command string | `mcp` |
| GitHub repo URL with `manifest.yaml` present | `python_plugin` |
| Other GitHub URL | Fetch content, re-detect |
| Unrecognized | Return candidates, user selects manually |

---

## Install Pipeline

```
User clicks Install / pastes URL
        ↓
Frontend: POST /api/plugins/install
  { url, type (optional), scope: "system" | "personal" }
        ↓
Backend: type detection (if type omitted)
        ↓
Adapter dispatch:
  mcp        → write to mcp_servers config table, open connection
  skill_md   → download .md, save to skills/ directory, hot-reload
  python_plugin → download .py/.zip, save to plugins/ directory, hot-reload
  langchain  → resolve package, register tool wrapper
        ↓
Write to installed_plugins table:
  { id, type, url, scope, installed_by, created_at }
        ↓
Return success → frontend refreshes list
```

Hot-reload is triggered after every install — no server restart required.

---

## Permission Model

| Action | System scope | Personal scope |
|--------|-------------|----------------|
| Install | Admin only | Any user |
| Uninstall | Admin only | Owner only |
| Visible to | All users | Owner only |
| Agent load order | System plugins load first | Personal plugins overlay |

**Storage paths:**
- System: `~/.jarvis/plugins/system/`
- Personal: `~/.jarvis/plugins/users/{user_id}/`

When the agent initializes, it loads system plugins first, then overlays the current user's personal plugins. If a personal plugin has the same name as a system plugin, the personal one takes precedence.

---

## Database

New table: `installed_plugins`

```sql
CREATE TABLE installed_plugins (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL,          -- mcp | skill_md | python_plugin | langchain
    install_url TEXT NOT NULL,
    scope       TEXT NOT NULL,          -- system | personal
    installed_by UUID REFERENCES users(id),
    created_at  TIMESTAMPTZ DEFAULT now()
);
```

---

## Backend Changes

### New / modified files

| File | Change |
|------|--------|
| `registry/index.json` | New — curated skill registry |
| `app/services/skill_market.py` | Modify `fetch_registry()` to load from `registry/index.json` |
| `app/plugins/type_detector.py` | New — URL → type detection logic |
| `app/plugins/adapters/mcp.py` | New — MCP install adapter |
| `app/plugins/adapters/skill_md.py` | New — SKILL.md install adapter (extracts from existing loader) |
| `app/plugins/adapters/python_plugin.py` | New — .py/.zip install adapter (extracts from existing loader) |
| `app/plugins/adapters/langchain.py` | New — LangChain tool adapter |
| `app/api/plugins.py` | Modify `install_plugin_from_url` to use adapters + write DB |
| `alembic/versions/xxx_add_installed_plugins.py` | New migration |

### New API endpoint

`POST /api/plugins/install`
```json
{
  "url": "https://...",
  "type": "skill_md",       // optional, auto-detected if omitted
  "scope": "personal"       // "system" requires admin
}
```

---

## Frontend Changes

### `SkillMarketPage.vue`

- Load registry from `GET /api/plugins/market/skills` (now returns real data)
- Add category filter tabs: All / MCP / Skill / Plugin / LangChain
- Each card: **Install as System** (admin only, greyed out for non-admin) / **Install for Me**
- Add **「+ Install from URL」** button → opens install modal

### Install Modal (new component: `InstallFromUrlModal.vue`)

1. Paste input field
2. Auto-detect indicator: "Detected as: SKILL.md ✓" (live as user types)
3. Scope selector: ○ Personal  ○ System (System disabled for non-admin)
4. Confirm button → calls `POST /api/plugins/install`

### `PluginsPage.vue`

- Split into two sections: **System Plugins** (admin can uninstall) / **My Plugins** (owner can uninstall)
- Each entry shows type badge: `MCP` / `Skill` / `Plugin`

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| URL unreachable | Return 400 with "Could not fetch URL" |
| Type undetectable | Return candidates list, frontend shows manual selector |
| Install fails (bad format) | Return 422 with reason, nothing written to DB |
| Personal install of system-only skill | Return 403 |
| Admin-only endpoint called by non-admin | Return 403 (existing `get_admin_user` dep) |

---

## Out of Scope

- Skill ratings / reviews
- Versioning / upgrade flow (install always gets latest)
- Sandboxed execution of untrusted Python plugins (existing sandbox handles code execution; plugin loading itself is trusted)
- Publishing skills to the registry from within JARVIS UI (community contributes via GitHub PR)
