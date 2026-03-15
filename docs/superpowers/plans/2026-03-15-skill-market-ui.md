# Skill Market UI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a visually appealing "Skill Market" page where users can browse, search, and install AI skills from the cloud registry.

**Architecture:** 
1. New `SkillMarketPage.vue` component.
2. Update `PluginsPage.vue` to include a link to the Market or integrate it as a tab.
3. UI state to track installation progress and local status.

**Tech Stack:** Vue 3, Tailwind CSS, Lucide Icons.

---

## Chunk 1: Market Page & Navigation

**Files:**
- Create: `frontend/src/pages/SkillMarketPage.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/pages/PluginsPage.vue`

- [ ] **Step 1: Add Market Route**
  In `frontend/src/router/index.ts`, add `/market` route mapping to `SkillMarketPage.vue`.

- [ ] **Step 2: Update Plugins Page Header**
  In `PluginsPage.vue`, add a "Browse Market" button that navigates to `/market`.

- [ ] **Step 3: Implement Basic Market Grid**
  In `SkillMarketPage.vue`, fetch skills from `/api/plugins/market/skills` and render them as cards.

- [ ] **Step 4: Commit**
  Run: `git add frontend/ && git commit -m "feat(frontend): add skill market page and navigation"`

---

## Chunk 2: Installation UI & Polish

**Files:**
- Modify: `frontend/src/pages/SkillMarketPage.vue`

- [ ] **Step 1: Implement Install/Uninstall Actions**
  Add click handlers for the Install/Uninstall buttons on each card.
  Call `POST /api/plugins/market/install/{id}?md_url=...` and `DELETE /api/plugins/market/uninstall/{id}`.

- [ ] **Step 2: Add Loading & Success States**
  Show a spinner on the button during installation. Show a "Installed" badge once complete.

- [ ] **Step 3: Implement Search & Filtering**
  Add a search bar to filter skills by name or author.

- [ ] **Step 4: Final Checks & Push**
  Run: `cd frontend && bun run type-check && bun run lint:fix`
  Run: `git add frontend/src/pages/SkillMarketPage.vue && git commit -m "feat(frontend): implement skill installation UI and search"`
  Run: `git push origin HEAD`
