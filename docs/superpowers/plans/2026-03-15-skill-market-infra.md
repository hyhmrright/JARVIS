# Skill Market Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend infrastructure to discover, download, and install AI skills from a remote registry. This allows users to extend JARVIS's capabilities without manual file management.

**Architecture:** 
1. `SkillRegistry` service in the backend fetches a curated JSON list of skills from a remote URL (e.g., GitHub).
2. `SkillManager` handles downloading `SKILL.md` files into a dedicated `installed_skills` directory.
3. The existing `plugin_registry` is updated to watch the `installed_skills` directory for hot-reloading.

**Tech Stack:** FastAPI, aiohttp, Python file I/O.

---

## Chunk 1: Remote Registry & Download Logic

**Files:**
- Create: `backend/app/services/skill_market.py`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Add Config for Registry URL**
  In `backend/app/core/config.py`, add `SKILL_REGISTRY_URL` (defaulting to a placeholder GitHub raw URL).

- [ ] **Step 2: Implement SkillRegistry Service**
  In `backend/app/services/skill_market.py`, create a class to:
  - Fetch the remote JSON list.
  - Download a `SKILL.md` from a given URL.
  - List locally installed skills.

- [ ] **Step 3: Define Skill Metadata Model**
  Use Pydantic to define the structure of a Market Skill (id, name, description, author, version, md_url).

- [ ] **Step 4: Commit**
  Run: `git add backend/ && git commit -m "feat(backend): add skill market service for discovery and download"`

---

## Chunk 2: Installation & Hot-Reloading

**Files:**
- Modify: `backend/app/plugins/loader.py`
- Modify: `backend/app/api/plugins.py`

- [ ] **Step 1: Update Plugin Loader to watch Dynamic Skills**
  Modify `backend/app/plugins/loader.py` to also load skills from a `data/installed_skills` directory.
  Ensure it can be re-triggered (hot-reload) without restarting the server.

- [ ] **Step 2: Implement Install API**
  In `backend/app/api/plugins.py`, add `POST /market/install/{skill_id}`.
  This calls the `SkillManager` to download the file and then triggers a plugin reload.

- [ ] **Step 3: Implement Uninstall API**
  Add `DELETE /market/install/{skill_id}` to remove the local file.

- [ ] **Step 4: Commit**
  Run: `git add backend/ && git commit -m "feat(backend): support dynamic skill installation and hot-reloading"`

---

## Chunk 3: Discovery API

**Files:**
- Modify: `backend/app/api/plugins.py`

- [ ] **Step 1: Implement Market List API**
  Add `GET /market/skills` to return the list of available skills from the remote registry, merged with their local installation status.

- [ ] **Step 2: Run Backend Tests**
  Run: `cd backend && uv run pytest tests/`
  *Note: Might need to mock the remote registry call in tests.*

- [ ] **Step 3: Commit & Push**
  Run: `git add backend/ && git commit -m "feat(backend): add public market API for skill discovery"`
  Run: `git push origin HEAD`
