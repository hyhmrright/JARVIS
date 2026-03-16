# LLMOps Dashboard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide Workspace Admins with visual insights into AI usage, costs, and performance. Implement a dashboard with real-time charts for tokens, latency, and tool usage.

**Architecture:** 
1. Backend `UsageService` aggregates data from Postgres (`messages` and `audit_logs` tables).
2. Backend provides a `/usage/stats` endpoint with time-series data.
3. Frontend `UsagePage.vue` is enhanced with ECharts components.

**Tech Stack:** FastAPI, SQLAlchemy, Vue 3, ECharts.

---

## Chunk 1: Backend Usage Aggregation

**Files:**
- Modify: `backend/app/api/usage.py`

- [ ] **Step 1: Implement Usage Stats API**
  Add `GET /api/usage/stats` that returns aggregated counts:
  - Tokens per day (last 7/30 days).
  - Messages per provider.
  - Average latency.
  - Most used tools.

- [ ] **Step 2: Add Workspace Filtering**
  Ensure stats are scoped to the user's workspace or personal usage.

- [ ] **Step 3: Commit**
  Run: `git add backend/ && git commit -m "feat(backend): implement aggregate usage statistics API"`

---

## Chunk 2: Frontend Dashboard UI

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/pages/UsagePage.vue`

- [ ] **Step 1: Install ECharts**
  Run: `cd frontend && bun add echarts vue-echarts`

- [ ] **Step 2: Design Dashboard Layout**
  In `UsagePage.vue`, add a grid of cards for high-level metrics (Total Tokens, Total Messages, etc.).

- [ ] **Step 3: Implement Charts**
  Add a Line chart for Token usage over time and a Pie chart for Provider distribution.

- [ ] **Step 4: Commit**
  Run: `git add frontend/ && git commit -m "feat(frontend): implement visual usage dashboard with echarts"`

---

## Chunk 3: Final Polish & Master Merge

**Files:**
- Modify: `GEMINI.md`

- [ ] **Step 1: Update GEMINI.md**
  Reflect the new architecture and capabilities in the project documentation.

- [ ] **Step 2: Master Verification**
  Run all project tests and linting.

- [ ] **Step 3: Final Push**
  Run: `git push origin HEAD`
  Create the final PR for the Epic.
