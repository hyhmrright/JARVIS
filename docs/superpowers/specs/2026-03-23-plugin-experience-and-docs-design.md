# Plugin Experience & Documentation — Design Spec
_2026-03-23_

## Context

JARVIS has a working plugin/skill install backend and two frontend pages (PluginsPage, SkillMarketPage),
but the experience is fragmented: install lives only on the market page, the plugins page has no install
entry, and installed-skill state is never reflected back in the market catalog. There is also no user
or developer documentation beyond the top-level README.

This spec covers two work streams:
1. **Plugin Experience** — connect the install→manage loop between SkillMarketPage and PluginsPage
2. **Documentation** — create structured user and developer guides

---

## 1. Plugin Experience

### 1.1 Problem Statement

| Gap | Impact |
|-----|--------|
| PluginsPage has no "install" entry point | Users must navigate to /market to install anything |
| SkillMarketPage never shows which skills are already installed | Users may install duplicates; no visual feedback after install |
| InstallFromUrlModal is only accessible from /market | Private/unlisted skills can't be installed from the main plugins hub |

### 1.2 Approach: Enhance Existing Pages (Option B)

Keep the two-page structure. PluginsPage is the **management hub**; SkillMarketPage is the **catalog browser**.

#### PluginsPage changes

1. **Add "Install" button** in the page header alongside the existing "Browse Market" button.
   - Clicking opens the existing `InstallFromUrlModal` (import and reuse, zero new component).
   - On successful install, call `loadInstalledPlugins()` to refresh the installed section.

2. **Installed section already exists** — no structural change needed. Verify it refreshes correctly.

#### SkillMarketPage changes

1. **Fetch installed list on mount** alongside `loadSkills()`. Store as `installedUrls: Set<string>`.
2. **Per-card installed state**: for each skill, check `skill.install_url` against `installedUrls`.
3. **Visual treatment**:
   - If installed: show green "Installed" badge; disable install button with "Installed ✓" label.
   - If not installed: current behavior unchanged.
4. **Refresh after install**: after `installSkill()` succeeds, re-fetch installed list to update badges.

### 1.3 Component / File Impact

| File | Change | Scope |
|------|--------|-------|
| `frontend/src/pages/PluginsPage.vue` | Add `InstallFromUrlModal` import + "Install" header button + refresh hook | ~20 lines |
| `frontend/src/pages/SkillMarketPage.vue` | Add installed-state fetch + badge rendering + button disable logic | ~30 lines |
| `frontend/src/api/plugins.ts` | No changes — `marketApi.listInstalled()` already exists | — |
| `frontend/src/components/InstallFromUrlModal.vue` | No changes — already handles install and emits `@installed` | — |

### 1.4 i18n Keys Required

```
// en.json additions (all other locales mirror)
plugins.install = "Install"
plugins.installFromUrl = "Install from URL"
skillMarket.installed = "Installed"
skillMarket.alreadyInstalled = "Installed ✓"
```

Locales to update: zh, en, ja, ko, fr, de (6 files).

### 1.5 No Backend Changes Required

All necessary endpoints already exist:
- `POST /api/plugins/install` — unified install
- `GET /api/plugins/installed` — list installed (used by `marketApi.listInstalled()`)

---

## 2. Documentation

### 2.1 Problem Statement

The README covers feature bullets but not how to use them. There is no:
- Getting-started walkthrough for new self-hosters
- Step-by-step plugin/skill installation guide
- Plugin SDK guide for developers who want to extend JARVIS

### 2.2 Structure

```
docs/
  user-guide/
    getting-started.md     # deploy + first login + first conversation
    plugins-and-skills.md  # how to browse, install, configure, uninstall
    rag-knowledge-base.md  # upload docs, workspace collections, RAG in chat
    workflows.md           # Workflow Studio walkthrough
  developer-guide/
    plugin-sdk.md          # write a Python plugin; SDK API reference
```

Five files. Scope is deliberately minimal — cover the highest-value gaps first.

### 2.3 Content Outline per File

#### `getting-started.md`
- Prerequisites (Docker, API keys)
- `git clone` → `bash scripts/init-env.sh` → `docker compose up -d`
- First login, register, configure LLM API key in Settings
- Send first message, try a tool call

#### `plugins-and-skills.md`
- Concept: plugin vs skill vs MCP server
- Install from Skill Market (browse catalog, click Install)
- Install from URL (private/unlisted plugins, npx MCP servers)
- Configure a plugin (API keys, enable/disable tools)
- Uninstall

#### `rag-knowledge-base.md`
- Upload a document (PDF, TXT, MD, DOCX)
- Ask a question that triggers RAG
- Workspace collections (how workspace RAG differs from personal)
- Ingest from URL

#### `workflows.md`
- Open Workflow Studio
- Create a node, connect edges
- Run/test a workflow
- Save and trigger from chat

#### `plugin-sdk.md`
- What a Python plugin is (directory structure, `plugin.yaml`, `plugin.py`)
- Minimal working example
- `sdk.py` API: `PluginContext`, `register_tool`, `get_config`
- Publishing to a registry (self-hosted registry format)

### 2.4 Tone and Format

- English primary (matches README language)
- Concrete commands and screenshots references rather than abstract descriptions
- Each file starts with a one-paragraph summary and a prerequisites list
- Code blocks for all shell commands and config snippets

---

## 3. Verification

### Plugin Experience
- [ ] PluginsPage header shows "Install" button
- [ ] Clicking "Install" opens InstallFromUrlModal
- [ ] After install completes, installed section refreshes without page reload
- [ ] SkillMarketPage shows "Installed ✓" for already-installed skills on load
- [ ] SkillMarketPage updates badge immediately after installing a skill
- [ ] All 6 locale files contain the new i18n keys

### Documentation
- [ ] `docs/user-guide/getting-started.md` covers deploy-to-first-message flow end-to-end
- [ ] `docs/user-guide/plugins-and-skills.md` covers all install paths (market, URL, npx)
- [ ] `docs/developer-guide/plugin-sdk.md` has a working minimal plugin example
- [ ] README links to the new docs

---

## 4. Out of Scope

- Merging PluginsPage and SkillMarketPage into one page (Option A)
- A hosted documentation site (Docusaurus/VitePress)
- Plugin rating, comments, or versioning in the market
- Video tutorials or interactive walkthroughs
